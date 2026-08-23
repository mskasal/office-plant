#include "esp_log.h"
#include "sleep_wake.h"
#include "moisture_sensor.h"
#include "ieee802154_radio.h"
#include "protocol_frame.h"

static const char *TAG = "main";

#define TEST_NODE_SHORT_ADDRESS 0x0001
#define TEST_WAKE_INTERVAL_SEC  30

/* Placeholder threshold: roughly the midpoint of the 12-bit ADC range
 * (0-4095). Task 4, Step 4 logs real dry/wet raw values from the actual
 * sensor hardware — replace this constant with the midpoint between those
 * two measured values once available. This is a calibration input from
 * real hardware, not an unresolved design decision: the code path, the
 * logging, and the comparison are all fully specified now. */
#define MOISTURE_DRY_THRESHOLD_RAW 2000

void app_main(void) {
    sleep_wake_log_boot();

    moisture_sensor_init();
    int raw = moisture_sensor_read_raw();
    moisture_sensor_deinit();

    ieee802154_radio_init(TEST_NODE_SHORT_ADDRESS);

    data_frame_t reading = {
        .sender_id = TEST_NODE_SHORT_ADDRESS,
        .needs_water = (raw < MOISTURE_DRY_THRESHOLD_RAW) ? NEEDS_WATER_TRUE : NEEDS_WATER_FALSE,
        .battery_pct = 100, /* battery-voltage ADC channel is out of scope for M1 */
        .timestamp = 0,     /* real clock sync arrives with the hub in M3/M4 */
    };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t len = encode_data_frame(&reading, buf);
    ieee802154_radio_send(buf, (uint8_t)len);
    ESP_LOGI(TAG, "sent DATA frame: raw=%d needs_water=%d", raw, reading.needs_water);

    sleep_wake_go_to_sleep(TEST_WAKE_INTERVAL_SEC);
}
