#include "ieee802154_radio.h"
#include <string.h>
#include "protocol_frame.h"
#include "esp_ieee802154.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

static const char *TAG = "ieee802154_radio";

typedef struct {
    uint8_t len;
    uint8_t data[PROTOCOL_FRAME_MAX_LEN];
    int8_t rssi;
} radio_rx_item_t;

static QueueHandle_t s_rx_queue = NULL;

/* Registered via esp_ieee802154_event_callback_list_register — this is the
 * pattern ESP-IDF's own OpenThread radio port uses (confirmed by reading
 * components/openthread/src/port/esp_openthread_radio.c). We do NOT define a
 * function literally named esp_ieee802154_receive_done; that's a separate,
 * legacy weak-symbol mechanism this plan does not use. */
static void radio_on_receive_done(uint8_t *frame, esp_ieee802154_frame_info_t *frame_info) {
    /* frame[0] is the PHY length byte (payload + 2-byte hw-appended FCS);
     * frame[1..] is our protocol payload. */
    uint8_t payload_len = frame[0] - 2;
    if (payload_len > PROTOCOL_FRAME_MAX_LEN) {
        payload_len = PROTOCOL_FRAME_MAX_LEN;
    }
    radio_rx_item_t item;
    item.len = payload_len;
    memcpy(item.data, frame + 1, payload_len);
    item.rssi = frame_info->rssi;

    BaseType_t higher_priority_task_woken = pdFALSE;
    xQueueSendFromISR(s_rx_queue, &item, &higher_priority_task_woken);
    if (higher_priority_task_woken) {
        portYIELD_FROM_ISR();
    }
}

static void radio_on_transmit_done(const uint8_t *frame, const uint8_t *ack, esp_ieee802154_frame_info_t *ack_frame_info) {
    (void)frame; (void)ack; (void)ack_frame_info;
    ESP_LOGD(TAG, "transmit done");
}

static void radio_on_transmit_failed(const uint8_t *frame, esp_ieee802154_tx_error_t error) {
    (void)frame;
    ESP_LOGW(TAG, "transmit failed, error=%d", (int)error);
}

void ieee802154_radio_init(uint16_t short_address) {
    s_rx_queue = xQueueCreate(8, sizeof(radio_rx_item_t));

    esp_ieee802154_event_cb_list_t cb_list = {
        .rx_done_cb = radio_on_receive_done,
        .tx_done_cb = radio_on_transmit_done,
        .tx_failed_cb = radio_on_transmit_failed,
    };
    ESP_ERROR_CHECK(esp_ieee802154_event_callback_list_register(cb_list));

    ESP_ERROR_CHECK(esp_ieee802154_enable());
    ESP_ERROR_CHECK(esp_ieee802154_set_promiscuous(true));
    ESP_ERROR_CHECK(esp_ieee802154_set_channel(RADIO_CHANNEL));
    ESP_ERROR_CHECK(esp_ieee802154_set_panid(RADIO_PAN_ID));
    ESP_ERROR_CHECK(esp_ieee802154_set_short_address(short_address));
    ESP_ERROR_CHECK(esp_ieee802154_set_txpower(RADIO_TX_POWER_DBM));
    ESP_ERROR_CHECK(esp_ieee802154_receive());

    ESP_LOGI(TAG, "radio ready: channel=%d panid=0x%04x addr=0x%04x",
             RADIO_CHANNEL, RADIO_PAN_ID, short_address);
}

void ieee802154_radio_send(const uint8_t *frame, uint8_t frame_len) {
    uint8_t tx_buf[1 + PROTOCOL_FRAME_MAX_LEN];
    tx_buf[0] = frame_len + 2; /* PHY length: payload + 2-byte hw-appended FCS */
    memcpy(tx_buf + 1, frame, frame_len);
    esp_err_t err = esp_ieee802154_transmit(tx_buf, false);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "transmit request failed: %d", (int)err);
    }
}

bool ieee802154_radio_receive(uint8_t *out_buf, uint8_t *out_len, int8_t *out_rssi, uint32_t timeout_ms) {
    radio_rx_item_t item;
    if (xQueueReceive(s_rx_queue, &item, pdMS_TO_TICKS(timeout_ms)) != pdTRUE) {
        return false;
    }
    memcpy(out_buf, item.data, item.len);
    *out_len = item.len;
    *out_rssi = item.rssi;
    return true;
}
