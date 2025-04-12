/***
 * Noptel LRF rangefinder sampler for the Flipper Zero
 * Version: 2.1
 *
 * Configuration saving / restoring
***/

/*** Routines ***/

/** Load saved configuration options
    Silently fail **/
void load_configuration(App *);

/** Save configuration options
    Silently fail **/
void save_configuration(App *);
