#include "esp_log.h"
#include "sleep_wake.h"

static const char *TAG = "main";

#define TEST_WAKE_INTERVAL_SEC 30  /* short interval for M1 bench observation;
                                       production interval is set by the hub
                                       at pairing time (M4), not hardcoded. */

void app_main(void) {
    sleep_wake_log_boot();
    ESP_LOGI(TAG, "M1 firmware boot");
    sleep_wake_go_to_sleep(TEST_WAKE_INTERVAL_SEC);
}
