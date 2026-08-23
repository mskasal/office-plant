#include "leaf_main.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sleep_wake.h"
#include "moisture_sensor.h"
#include "ieee802154_radio.h"
#include "protocol_frame.h"
#include "mesh_parent_select.h"

static const char *TAG = "leaf_main";

/* Bench-only hardcoded test address, distinct from M1's 0x0001 and the
 * root's 0x0000 (root_main.c) — real per-node addressing arrives with M4
 * provisioning. */
#define LEAF_SHORT_ADDRESS 0x0002
#define TEST_WAKE_INTERVAL_SEC 30
#define DISCOVERY_LISTEN_TIMEOUT_MS 2000
#define MAX_PARENT_CANDIDATES 8

/* Same placeholder as M1's main.c — still needs real dry/wet calibration
 * from hardware once available (see M1 plan Task 4, Step 4). */
#define MOISTURE_DRY_THRESHOLD_RAW 2000

static size_t listen_for_beacons(parent_candidate_t *candidates, size_t max_candidates) {
    size_t count = 0;
    TickType_t start = xTaskGetTickCount();

    for (;;) {
        uint32_t elapsed_ms = (xTaskGetTickCount() - start) * portTICK_PERIOD_MS;
        if (elapsed_ms >= DISCOVERY_LISTEN_TIMEOUT_MS || count >= max_candidates) {
            break;
        }
        uint32_t remaining_ms = DISCOVERY_LISTEN_TIMEOUT_MS - elapsed_ms;

        uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
        uint8_t len;
        int8_t rssi;
        if (!ieee802154_radio_receive(buf, &len, &rssi, remaining_ms)) {
            break; /* timed out with nothing more arriving */
        }
        if (decode_frame_type(buf, len) != FRAME_TYPE_BEACON) {
            continue;
        }
        beacon_frame_t beacon;
        if (decode_beacon_frame(buf, len, &beacon) != 0) {
            continue;
        }
        candidates[count].sender_id = beacon.sender_id;
        candidates[count].hop_count = beacon.hop_count;
        candidates[count].rssi = rssi;
        count++;
    }
    return count;
}

void leaf_main_run(void) {
    sleep_wake_log_boot();
    ieee802154_radio_init(LEAF_SHORT_ADDRESS);

    parent_candidate_t candidates[MAX_PARENT_CANDIDATES];
    size_t candidate_count = listen_for_beacons(candidates, MAX_PARENT_CANDIDATES);

    int parent_id = select_parent(candidates, candidate_count);
    if (parent_id < 0) {
        ESP_LOGW(TAG, "no parent found this wake cycle");
        sleep_wake_go_to_sleep(TEST_WAKE_INTERVAL_SEC);
        return;
    }
    ESP_LOGI(TAG, "selected parent=0x%04x", (unsigned)parent_id);

    join_frame_t join = {
        .sender_id = LEAF_SHORT_ADDRESS,
        .target_parent_id = (uint16_t)parent_id,
    };
    uint8_t join_buf[PROTOCOL_FRAME_MAX_LEN];
    size_t join_len = encode_join_frame(&join, join_buf);
    ieee802154_radio_send(join_buf, (uint8_t)join_len);
    ESP_LOGI(TAG, "sent JOIN to parent=0x%04x", (unsigned)parent_id);

    moisture_sensor_init();
    int raw = moisture_sensor_read_raw();
    moisture_sensor_deinit();

    data_frame_t reading = {
        .sender_id = LEAF_SHORT_ADDRESS,
        .needs_water = (raw < MOISTURE_DRY_THRESHOLD_RAW) ? NEEDS_WATER_TRUE : NEEDS_WATER_FALSE,
        .battery_pct = 100, /* battery-voltage ADC channel is out of scope, same as M1 */
        .timestamp = 0,     /* real clock sync arrives with the hub in M3/M4 */
    };
    uint8_t data_buf[PROTOCOL_FRAME_MAX_LEN];
    size_t data_len = encode_data_frame(&reading, data_buf);
    ieee802154_radio_send(data_buf, (uint8_t)data_len);
    ESP_LOGI(TAG, "sent DATA frame: raw=%d needs_water=%d", raw, reading.needs_water);

    sleep_wake_go_to_sleep(TEST_WAKE_INTERVAL_SEC);
}
