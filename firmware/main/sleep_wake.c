#include "sleep_wake.h"
#include <inttypes.h>
#include "esp_sleep.h"
#include "esp_log.h"

static const char *TAG = "sleep_wake";

/* ESP32-C6 only has RTC FAST memory, so RTC_DATA_ATTR is the correct
 * attribute to persist this counter across deep sleep (confirmed against
 * esp_sleep.h's ESP32-C6-specific documentation). */
RTC_DATA_ATTR static uint32_t s_boot_count = 0;

void sleep_wake_log_boot(void) {
    s_boot_count++;
    esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
    ESP_LOGI(TAG, "boot #%" PRIu32 ", wakeup cause = %d", s_boot_count, (int)cause);
}

void sleep_wake_go_to_sleep(uint32_t seconds) {
    ESP_LOGI(TAG, "sleeping for %" PRIu32 " seconds", seconds);
    esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
    esp_deep_sleep_start();
}
