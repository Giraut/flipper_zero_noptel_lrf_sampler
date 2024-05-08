#!/usr/bin/python3
# PYTHON_ARGCOMPLETE_OK
"""Noptel LRF rangefinder sampler for the Flipper Zero
Version: 1.7

Companion utility to connect to the Flipper Zero CLI and decode LRF serial
traffic traces generated by the USB serial passthrough function

The utility needs the USB serial passthrough to be configured on channel 1, so
the Flipper Zero CLI is still available on channel 0

If the LRF class is not present or can't be imported, the utility performs basic
recognition of LRF commands sent to the LRF and responses sent back by the LRF
(standalone decoder)

If the LRF class is present and imported, the utility decodes all the frames in
full and displays the decoded values

Usage:

python lrf_traffic_tracer.py /dev/ttyACMx [-r|-s] (Linux)
python lrf_traffic_tracer.py COMx [-r|-s]         (Windows)

/dev/ttyACMx or COMx is the COM port corresponding to the Flipper Zero's CLI

-r turns off the decoder and displays the traffic bytes raw instead
-s forces the use of the standalone decoder even if the LRF class is available
"""

## Parameters
#

cli_serial_device_baudrate = 921600 #bps
max_line_width = 79 #characters



## Modules
#

import re
import sys
import argparse
from time import sleep
from serial import Serial
import serial.tools.list_ports

# Optional bash completion support
try:
  import argcomplete
  has_argcomplete = True
except:
  has_argcomplete = False

# Optional LRF class
try:
  from lrfclass.full.lrf import LRF
  has_lrfclass = True
except:
  try:
    from lrfclass.lrf import LRF
    has_lrfclass = True
  except:
    has_lrfclass = False



## Defines
#

TO_LRF = 0
FROM_LRF = 1
DOT = b"."[0]



## Classes
#

class StandaloneBasicLRFTrafficDecoder:
  """Standalone basic LRF traffic decoder, for use when the LRF class is not
  available
  """

  ## LRF command and response frame patterns
  lrf_frame_patterns = (

  # Command frame patterns
  {
    "SMM": b"\xc3.",
    "SMM_WITH_STATUS": b"\x12.",
    "SMM_LOW_VIS": b"\xd3.",
    "QUICK_SMM": b"\xdd..",
    "CMM": b"\xda..",
    "CMM_BREAK": b"\xc6.",
    "EXEC_RANGE_MEAS": b"\xcc....",
    "STATUS_QUERY": b"\xc7.",
    "SET_PTR_MODE": b"\xc5..",
    "ASK_RANGE_WIN": b"\x30.",
    "SET_MIN_RANGE": b"\x31...",
    "SET_MAX_RANGE": b"\x32...",
    "SET_BAUDRATE": b"\xc8..",
    "SEND_ID_FRAME": b"\xc0.",
    "SEND_INFO_FRAME": b"\xc2.",
    "RST_RS_ERR_CTR": b"\xcb."
  },

  # Response frame patterns
  {
    "RESP_SMM": b"\x59\xc3.......",
    "RESP_SMM_WITH_STATUS": b"\x59\x12........",
    "RESP_SMM_LOW_VIS": b"\x59\xd3.......",
    "RESP_QUICK_SMM": b"\x59\xdd.......",
    "RESP_CMM": b"\x59\xda.......",
    "RESP_CMM_BREAK": b"\x59\xc6\x3c.",
    "RESP_EXEC_RANGE_MEAS": b"\x59\xcc....................",
    "RESP_STATUS_QUERY": b"\x59\xc7....",
    "RESP_SET_PTR_MODE": b"\x59\xc5\x3c.",
    "RESP_ASK_RANGE_WIN": b"\x59\x30.....",
    "RESP_SET_MIN_RANGE": b"\x59\x31\x3c.",
    "RESP_SET_MAX_RANGE": b"\x59\x32\x3c.",
    "RESP_SET_BAUDRATE": b"\x59\xc8\x3c.",
    "RESP_SEND_ID_FRAME": b"\x59\xc0...............\x0d\x0a..............."
  				b"\x0d\x0a..........\x0d\x0a............"
	  			b"\x0d\x0a..\x3a..\x3a..\x0d\x0a.",
    "RESP_SEND_INFO_FRAME": b"\x59\xc2.......\x01........"
				b"......................",
    "RESP_RST_RS_ERR_CTR": b"\x59\xcb\x3c."
  })



  def __init__(self):
    """Initialize the decoder
    """

    self.lrf_frame_patterns_li = [{k: len(self.lrf_frame_patterns[d][k]) - 1 \
					for k in self.lrf_frame_patterns[d]} \
					for d in (TO_LRF, FROM_LRF)]
    self.bytes_buf = [[], []]
    self.potential_frame_matches = [set(self.lrf_frame_patterns[d]) \
					for d in (TO_LRF, FROM_LRF)]
    self.frame_i = [0, 0]

    self.chars_in_line = 0



  def print_decoded_traffic(self, timestamp, d, data):
    """Decode traffic bytes and display the decoded frame names
    """

    # Decode the bytes
    for b in data:

      # Add the byte to the frame buffer
      self.bytes_buf[d].append(b)

      # Check potential matching frames for this byte
      for f in set(self.potential_frame_matches[d]):

        # The potential matching frame is too small
        if self.lrf_frame_patterns_li[d][f] < self.frame_i[d]:
          self.potential_frame_matches[d].remove(f)

        # Non-matching character in the potential matching frame
        elif self.lrf_frame_patterns[d][f][self.frame_i[d]] not in (DOT, b):
          self.potential_frame_matches[d].remove(f)

        # Matching frame
        elif self.lrf_frame_patterns_li[d][f] == self.frame_i[d]:

          # The frame is an LRF response but the checksum is incorrect
          if d == FROM_LRF and self._checksum(self.bytes_buf[d][:-1]) != \
				self.bytes_buf[d][-1]:
            self.potential_frame_matches[d].remove(f)
            continue

          # Print the name of the matching frame
          if self.chars_in_line:
            print()
          print("{}: {}LRF: {}".  format(timestamp, "<>"[d], f))
          self.chars_in_line = 0

          # Reset the bytes buffer and the set of potential matching frames
          self.bytes_buf[d].clear()
          self.frame_i[d] = 0
          self.potential_frame_matches[d] = set(self.lrf_frame_patterns[d])

          break

      # No potential matches found
      else:

        # No potential matches left
        if not self.potential_frame_matches[d]:

          # Print the raw bytes
          for b in self.bytes_buf[d]:

            sb = " {:02x}".format(b)
            lb = len(sb)

            if not self.chars_in_line or \
			self.chars_in_line + lb > max_line_width:

              if self.chars_in_line:
                print()

              sh = "{}: {}LRF:".format(timestamp, "<>"[d])
              print(sh, end = "")
              self.chars_in_line = len(sh)

            print(sb, end = "")
            self.chars_in_line += lb

          # Reset the bytes buffer and the set of potential matching frames
          self.bytes_buf[d] = []
          self.frame_i[d] = 0
          self.potential_frame_matches[d] = set(self.lrf_frame_patterns[d])

          continue

        self.frame_i[d] += 1



  def _checksum(self, data):
    """Calculate the checksum of a block of data
    """

    return (sum([c for c in data]) & 0xff) ^ 0x50



class FullLRFTrafficDecoder:
  """LRF traffic decoder based on the LRF class that decodes all the frame types
  and all the values they contain
  """

  def __init__(self):
    """Initialize the decoder
    """

    self.buf = [b"", b""]
    self.nb_bytes_read = [0, 0]

    self.direction = None

    self.lrf = LRF()
    self.lrf.last_command_read_memory_pagecnt = 0

    self.chars_in_line = True



  def _sim_read(self, nb_bytes, timeout):
    """Simulated serial read function
    """

    offset = self.nb_bytes_read[self.direction]
    self.nb_bytes_read[self.direction] += nb_bytes

    return self.buf[self.direction][offset : self.nb_bytes_read[self.direction]]



  def print_decoded_traffic(self, timestamp, d, data):
    """Decode traffic bytes and display the decoded frame names
    """

    self.direction = d
    self.buf[d] += data

    get_frame = self.lrf.get_ext_command if d == TO_LRF else \
		self.lrf.get_lrf_response

    # Try to decode frame until we run out of bytes to decode
    while True:

      try:
        r = get_frame(altreadfct = self._sim_read)

      # We don't have all the bytes yet
      except TimeoutError:
        self.nb_bytes_read[d] = 0
        break

      # The decoder threw an error: print the offending bytes and the error
      except ValueError as e:
        print("{}: {}LRF: {}: {}".
		format(timestamp, "<>"[d], " ".join(
			["{:02x}".format(v) \
				for v in self.buf[d][:self.nb_bytes_read[d]]]),
			e))
        r = None

      # If we got a decoded frame, print it
      if r is not None:
        print("{}: {}LRF: {}".format(timestamp, "<>"[d], r))

      # Remove the read bytes from the buffer
      self.buf[d] = self.buf[d][self.nb_bytes_read[d]:]
      self.nb_bytes_read[d] = 0



class NullLRFTrafficDecoder:
  """Decoder that doesn't decode anything, only prints the raw bytes
  """

  def __init__(self):
    """Initialize the "decoder"
    """

    self.chars_in_line = True



  def print_decoded_traffic(self, timestamp, d, data):
    """Decode traffic bytes and display the decoded frame names
    """

    # Print the raw bytes
    for b in data:

      sb = " {:02x}".format(b)
      lb = len(sb)

      if not self.chars_in_line or \
			self.chars_in_line + lb > max_line_width:

        if self.chars_in_line:
          print()

        sh = "{}: {}LRF:".format(timestamp, "<>"[d])
        print(sh, end = "")
        self.chars_in_line = len(sh)

      print(sb, end = "")
      self.chars_in_line += lb



## Routines
#

def device_completer(**kwargs):
  """Argcomplete completer that returns all serial port device names
  """

  return sorted([p[0] for p in serial.tools.list_ports.comports(
							include_links = True)])



## Main routine
#

def main():

  # Parse the command line arguments
  argparser = argparse.ArgumentParser()

  argparser.add_argument(
	  "cli_serial_device",
	  help = "Serial device corresponding to the Flipper Zero CLI "
			"(e.g. /dev/ttyACM0 on Linux/Unix, COM1 on Windows)",
	  type = str
	).completer = device_completer

  mutexargs = argparser.add_mutually_exclusive_group(required = False)

  mutexargs.add_argument(
	  "-s", "--standalone-decoder",
	  help = "Use the standalone decoder even if the LRF class is "
			"available",
	  action = "store_true"
	)

  mutexargs.add_argument(
	  "-r", "--raw",
	  help = "Don't decode the LRF traffic and simply display the "
			"raw bytes",
	  action = "store_true"
	)

  if has_argcomplete:
    argcomplete.autocomplete(argparser, always_complete_options = False)

  args = argparser.parse_args()

  print()
  print("LRF traffic tracer")
  print("------------------")
  print()

  # Initialize the correct traffic decoder
  if args.raw:
    decoder = NullLRFTrafficDecoder()

  elif has_lrfclass and not args.standalone_decoder:
    decoder = FullLRFTrafficDecoder()
    print("Using the full LRF frame decoder")

  else:
    decoder = StandaloneBasicLRFTrafficDecoder()
    print("Using the standalone LRF frame decoder")

  # Precompiled regex for a trace log line from the USB serial passthrough
  re_passthru_log_line = re.compile("([0-9]+) .*\[noptel_lrf_sampler\] .*"
					"([<>])LRF:((?: [0-9a-zA-Z]{2})+)")

  print("Ctrl-C to exit...")
  print()

  clidev = None
  errcode = 0

  try:

    # Run until stopped by Ctrl-C
    while True:

      # Do we arrive here from a previous error? */
      if errcode:

        # Close the Flipper Zero's CLI device and wait a bit before trying to
        # open it again
        try:
          clidev.close()

        except:
          pass

        clidev = None

        print("Retrying in 2 seconds...")
        print()
        sleep(2)

      # Try to open the Flipper Zero's CLI device
      if clidev is None:

        try:
          clidev = Serial(args.cli_serial_device, cli_serial_device_baudrate,
				timeout = 0.2)

        except Exception as e:
          print("Error opening {}: {}".format(args.cli_serial_device, e))
          errcode = -1
          continue

        print("{} opened at {} bps".
		format(args.cli_serial_device, cli_serial_device_baudrate))
        errcode = 0

      try:

        # Read one line from the CLI
        while True:

          l = clidev.readline().rstrip().decode("ascii")
          if l:
            break

          # Timeout: send LF to the console if the curent line is not empty
          if decoder.chars_in_line:
            print()
            decoder.chars_in_line = 0

      except Exception as e:
        print("Error reading from {}: {}".format(args.cli_serial_device, e))
        errcode = -1
        continue

      # Did the CLI start or restart?
      if l.startswith("Welcome"):

        # Enable trace logging
        try:
          clidev.write(b"log trace\r")
          print("Trace log started")
          print()

        except Exception as e:
          print("Error writing to {}: {}".format(args.cli_serial_device, e))
          errcode = -1
          continue

      # Catch LRF serial traffic lines from the USB serial passthrough
      m = re_passthru_log_line.match(l)
      if m:

        timestamp = int(m[1])
        d = TO_LRF if m[2] == ">" else FROM_LRF
        data = bytes([int(v, 16) for v in m[3].split()])

        # Decode the received bytes and print the decoded information
        decoder.print_decoded_traffic(timestamp, d, data);

  except KeyboardInterrupt:
    print()
    print("Interrupted")

  finally:

    # Close the Flipper Zero's CLI
    if clidev is not None:
      try:
        clidev.close()
      except:
        pass

  return errcode



## Main program
#

if __name__ == "__main__":
  sys.exit(main())
