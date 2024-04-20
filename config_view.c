/***
 * Noptel LRF rangefinder sampler for the Flipper Zero
 * Version: 1.3
 *
 * Configuration view
***/

/*** Includes ***/
#include "config_view.h"
#include "noptel_lrf_sampler.h"



/*** Routines ***/

/** Frequency setting change function **/
void config_freq_change(VariableItem *item) {

  App *app = variable_item_get_context(item);
  SamplerModel *sampler_model = view_get_model(app->sample_view);
  uint8_t idx;

  /* Get the new frequency setting item index */
  idx = variable_item_get_current_value_index(item);

  /* Set the new frequency setting */
  sampler_model->config.freq = config_freq_values[idx];
  variable_item_set_current_value_text(item, config_freq_names[idx]);

  FURI_LOG_D(TAG, "Frequency setting change: %s", config_freq_names[idx]);
}



/** Buffering setting change function **/
void config_buf_change(VariableItem *item) {

  App *app = variable_item_get_context(item);
  SamplerModel *sampler_model = view_get_model(app->sample_view);
  uint8_t idx;

  /* Get the new buffering setting item index */
  idx = variable_item_get_current_value_index(item);

  /* Set the new buffering setting */
  sampler_model->config.buf = config_buf_values[idx];
  variable_item_set_current_value_text(item, config_buf_names[idx]);

  FURI_LOG_D(TAG, "Buffering setting change: %s", config_buf_names[idx]);
}



/** Beep option change function **/
void config_beep_change(VariableItem *item) {

  App *app = variable_item_get_context(item);
  SamplerModel *sampler_model = view_get_model(app->sample_view);
  uint8_t idx;

  /* Get the new beep option item index */
  idx = variable_item_get_current_value_index(item);

  /* Set the new beep option */
  sampler_model->config.beep = config_beep_values[idx] != 0;
  variable_item_set_current_value_text(item, config_beep_names[idx]);

  FURI_LOG_D(TAG, "Beep option change: %s", config_beep_names[idx]);
}
