#include "leaf_main.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sleep_wake.h"
#include "moisture_sensor.h"
#include "ieee802154_radio.h"
#include "protocol_frame.h"
#include "mesh_parent_select.h"
#include "node_identity.h"
#include "node_config.h"

static const char *TAG = "leaf_main";

#define DISCOVERY_LISTEN_TIMEOUT_MS 2000
#define MAX_PARENT_CANDIDATES 8

/* How long to listen for a piggybacked CONFIG frame after sending DATA
 * (spec Section 4.1: "applies any config pushed back down -> sleeps").
 * Short because the hub replies within the same window this node's own
 * DATA send just opened — it isn't waiting on a separate radio cycle. */
#define CONFIG_LISTEN_TIMEOUT_MS 1000

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

/* Listens briefly for a CONFIG frame targeting this node and applies it
 * (spec Section 4.1). Silently does nothing if none arrives — a node not
 * given a new config just keeps its current one, which is the expected
 * common case, not an error. */
static void listen_and_apply_config(uint16_t short_address) {
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    uint8_t len;
    int8_t rssi;
    if (!ieee802154_radio_receive(buf, &len, &rssi, CONFIG_LISTEN_TIMEOUT_MS)) {
        return;
    }
    if (decode_frame_type(buf, len) != FRAME_TYPE_CONFIG) {
        return;
    }
    config_frame_t config;
    if (decode_config_frame(buf, len, &config) != 0 || config.target_node_id != short_address) {
        return;
    }
    node_config_apply(config.wake_interval_sec, config.moisture_dry_threshold_raw);
}

void leaf_main_run(void) {
    sleep_wake_log_boot();
    uint16_t short_address = node_identity_get_short_address();
    uint32_t wake_interval_sec = node_config_get_wake_interval_sec();
    uint16_t moisture_dry_threshold_raw = node_config_get_moisture_dry_threshold_raw();
    ieee802154_radio_init(short_address);

    parent_candidate_t candidates[MAX_PARENT_CANDIDATES];
    size_t candidate_count = listen_for_beacons(candidates, MAX_PARENT_CANDIDATES);

    int parent_id = select_parent(candidates, candidate_count);
    if (parent_id < 0) {
        ESP_LOGW(TAG, "no parent found this wake cycle");
        sleep_wake_go_to_sleep(wake_interval_sec);
        return;
    }
    ESP_LOGI(TAG, "selected parent=0x%04x", (unsigned)parent_id);

    join_frame_t join = {
        .sender_id = short_address,
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
        .sender_id = short_address,
        .needs_water = (raw < moisture_dry_threshold_raw) ? NEEDS_WATER_TRUE : NEEDS_WATER_FALSE,
        .battery_pct = 100, /* battery-voltage ADC channel is out of scope, same as M1 */
        .timestamp = 0,     /* real clock sync arrives with the hub in M3/M4 */
    };
    uint8_t data_buf[PROTOCOL_FRAME_MAX_LEN];
    size_t data_len = encode_data_frame(&reading, data_buf);
    ieee802154_radio_send(data_buf, (uint8_t)data_len);
    ESP_LOGI(TAG, "sent DATA frame: raw=%d needs_water=%d", raw, reading.needs_water);

    listen_and_apply_config(short_address);

    /* Re-read in case listen_and_apply_config just changed it -- the
     * updated interval should govern this very sleep, not wait for next
     * wake to take effect. */
    sleep_wake_go_to_sleep(node_config_get_wake_interval_sec());
}
