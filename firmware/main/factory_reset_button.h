#ifndef FACTORY_RESET_BUTTON_H
#define FACTORY_RESET_BUTTON_H

#include <stdbool.h>

/* Configures the button GPIO as an input with pull-up and enables it as a
 * deep-sleep EXT1 wake source, so a press can wake the node outside its
 * normal RTC-timer schedule. Call once at boot, before any
 * esp_deep_sleep_start(). */
void factory_reset_button_enable_wakeup(void);

/* True if this boot's wakeup cause was the factory-reset button (as
 * opposed to the RTC timer or power-on). */
bool factory_reset_button_caused_wakeup(void);

/* Blocks (up to ~5.5s) polling the button GPIO to confirm it is genuinely
 * still held for FACTORY_RESET_HOLD_MS, debouncing against a brief bump
 * that triggered the EXT1 wake. Returns true if the hold was confirmed —
 * caller should then factory-reset and reboot into pairing mode; false if
 * released early, meaning the caller should resume its normal cycle. */
bool factory_reset_button_confirm_long_press(void);

#endif
