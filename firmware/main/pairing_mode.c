#include "pairing_mode.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ieee802154_radio.h"
#include "protocol_frame.h"
#include "node_identity.h"

static const char *TAG = "pairing_mode";

/* Pairing-mode radio address: unclaimed nodes have no assigned
 * short_address yet (that's what CLAIM grants), so the radio is
 * initialized with a fixed well-known pairing address rather than a real
 * per-node one. All unclaimed nodes share this address during setup;
 * BLINK targeting and CLAIM correlation use factory_id instead (below),
 * not radio addressing. */
#define PAIRING_RADIO_ADDRESS 0xFFFE

#define PAIRING_LISTEN_WINDOW_MS 500
#define PAIRING_CYCLE_INTERVAL_MS 2000

/* Bench-only placeholder GPIO for the setup-confirmation LED — the M4 plan
 * requires "blinks an LED for ~3s" but doesn't pin specific hardware.
 * ESP32-C6-DevKitC-1's onboard LED is an addressable WS2812 requiring the
 * led_strip component (out of scope here); this assumes a simple discrete
 * LED wired to this GPIO instead, to be confirmed against real board
 * wiring during M4's bench test — same caveat status as M1's ADC GPIO
 * note (developer-setup.md Section 6). */
#define BLINK_LED_GPIO GPIO_NUM_2
#define BLINK_DURATION_MS 3000

/* The M4 plan says BLINK/CLAIM target a node's "factory ID" (spec Section
 * 4.5's 64-bit factory-unique radio-MAC ID), but reuses JOIN's 5-byte/
 * 2x-uint16-field wire shape (protocol_frame.h) — a 64-bit ID doesn't fit
 * a uint16 field. Resolved here: factory_id is the low 16 bits of the
 * node's actual burned-in 802.15.4 MAC, unique enough for a 30-50 node
 * fleet and still satisfies "factory-unique, only used during the pairing
 * handshake" (spec Section 4.5) without widening the frame. */
static uint16_t get_factory_id(void) {
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_IEEE802154);
    return ((uint16_t)mac[4] << 8) | mac[5];
}

static void blink_led(void) {
    ESP_LOGI(TAG, "BLINK: driving LED for %d ms", BLINK_DURATION_MS);
    gpio_set_level(BLINK_LED_GPIO, 1);
    vTaskDelay(pdMS_TO_TICKS(BLINK_DURATION_MS));
    gpio_set_level(BLINK_LED_GPIO, 0);
}

static void send_announce(uint16_t factory_id) {
    announce_frame_t announce = { .factory_id = factory_id };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t len = encode_announce_frame(&announce, buf);
    ieee802154_radio_send(buf, (uint8_t)len);
}

/* Returns true once a valid CLAIM has been persisted (caller should stop
 * looping); false otherwise. */
static bool handle_frame(const uint8_t *buf, uint8_t len, uint16_t factory_id) {
    int type = decode_frame_type(buf, len);
    if (type == FRAME_TYPE_BLINK) {
        blink_frame_t blink;
        if (decode_blink_frame(buf, len, &blink) == 0 && blink.target_node_id == factory_id) {
            blink_led();
        }
        return false;
    }
    if (type == FRAME_TYPE_CLAIM) {
        /* CLAIM's 2-field shape (assigned_short_address, hub_id) has no
         * per-node targeting field, so every unclaimed node hears every
         * CLAIM. Safe within this milestone's scope because pairing mode
         * is a physically supervised setup step (spec Section 5: "place
         * new nodes near the hub") and the M4 bench test claims one node
         * at a time; a real multi-node-simultaneously-unclaimed race is a
         * known gap flagged here, not solved by this milestone. */
        claim_frame_t claim;
        if (decode_claim_frame(buf, len, &claim) == 0) {
            node_identity_set_claimed(claim.hub_id, claim.assigned_short_address);
            return true;
        }
    }
    return false;
}

void pairing_mode_run(void) {
    gpio_set_direction(BLINK_LED_GPIO, GPIO_MODE_OUTPUT);
    gpio_set_level(BLINK_LED_GPIO, 0);

    uint16_t factory_id = get_factory_id();
    ieee802154_radio_init(PAIRING_RADIO_ADDRESS);
    ESP_LOGI(TAG, "pairing mode: factory_id=0x%04x, listening %dms every %dms",
             factory_id, PAIRING_LISTEN_WINDOW_MS, PAIRING_CYCLE_INTERVAL_MS);

    for (;;) {
        send_announce(factory_id);

        uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
        uint8_t len;
        int8_t rssi;
        if (ieee802154_radio_receive(buf, &len, &rssi, PAIRING_LISTEN_WINDOW_MS)) {
            if (handle_frame(buf, len, factory_id)) {
                ESP_LOGI(TAG, "claimed — switching to normal scheduled cycle");
                return;
            }
        }

        vTaskDelay(pdMS_TO_TICKS(PAIRING_CYCLE_INTERVAL_MS - PAIRING_LISTEN_WINDOW_MS));
    }
}
