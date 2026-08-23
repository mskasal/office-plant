#include "esp_log.h"
#include "sleep_wake.h"
#include "moisture_sensor.h"

static const char *TAG = "main";

#define TEST_WAKE_INTERVAL_SEC 30

void app_main(void) {
    sleep_wake_log_boot();

    moisture_sensor_init();
    int raw = moisture_sensor_read_raw();
    moisture_sensor_deinit();
    ESP_LOGI(TAG, "moisture raw = %d", raw);

    sleep_wake_go_to_sleep(TEST_WAKE_INTERVAL_SEC);
}
