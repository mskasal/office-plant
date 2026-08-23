#include "root_main.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ieee802154_radio.h"
#include "protocol_frame.h"

static const char *TAG = "root_main";

/* Hop-count-0 root; matches the sim's HUB_ID=0 convention (sim/node.py).
 * Bench-only hardcoded address, same status as M1's TEST_NODE_SHORT_ADDRESS
 * — real per-node addressing arrives with M4 provisioning. */
#define ROOT_SHORT_ADDRESS 0x0000
#define BEACON_INTERVAL_MS 5000
#define RECEIVE_POLL_TIMEOUT_MS 200

static void send_beacon(void) {
    beacon_frame_t beacon = {
        .sender_id = ROOT_SHORT_ADDRESS,
        .hop_count = 0,
    };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t len = encode_beacon_frame(&beacon, buf);
    ieee802154_radio_send(buf, (uint8_t)len);
    ESP_LOGI(TAG, "sent BEACON hop_count=0");
}

static void log_received_frame(const uint8_t *buf, uint8_t len, int8_t rssi) {
    int type = decode_frame_type(buf, len);
    switch (type) {
        case FRAME_TYPE_JOIN: {
            join_frame_t join;
            if (decode_join_frame(buf, len, &join) == 0) {
                ESP_LOGI(TAG, "received JOIN sender=0x%04x target_parent=0x%04x rssi=%d",
                         join.sender_id, join.target_parent_id, rssi);
            }
            break;
        }
        case FRAME_TYPE_DATA: {
            data_frame_t data;
            if (decode_data_frame(buf, len, &data) == 0) {
                ESP_LOGI(TAG, "received DATA sender=0x%04x needs_water=%d battery_pct=%d rssi=%d",
                         data.sender_id, data.needs_water, data.battery_pct, rssi);
            }
            break;
        }
        case FRAME_TYPE_BEACON: {
            /* M2's two-board setup has only one beaconer (the root itself),
             * so this shouldn't fire — logged rather than silently dropped
             * in case a stray/rebooted second root is on the same channel. */
            beacon_frame_t beacon;
            if (decode_beacon_frame(buf, len, &beacon) == 0) {
                ESP_LOGI(TAG, "received BEACON sender=0x%04x hop_count=%d rssi=%d",
                         beacon.sender_id, beacon.hop_count, rssi);
            }
            break;
        }
        default:
            ESP_LOGW(TAG, "received unknown frame type=%d len=%d rssi=%d", type, len, rssi);
            break;
    }
}

void root_main_run(void) {
    ieee802154_radio_init(ROOT_SHORT_ADDRESS);
    ESP_LOGI(TAG, "root role started, beaconing every %d ms", BEACON_INTERVAL_MS);

    TickType_t last_beacon = xTaskGetTickCount();
    for (;;) {
        TickType_t now = xTaskGetTickCount();
        if ((now - last_beacon) * portTICK_PERIOD_MS >= BEACON_INTERVAL_MS) {
            send_beacon();
            last_beacon = now;
        }

        uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
        uint8_t len;
        int8_t rssi;
        if (ieee802154_radio_receive(buf, &len, &rssi, RECEIVE_POLL_TIMEOUT_MS)) {
            log_received_frame(buf, len, rssi);
        }
    }
}
