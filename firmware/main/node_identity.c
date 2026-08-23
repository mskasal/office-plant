#include "node_identity.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"

static const char *TAG = "node_identity";

#define NVS_NAMESPACE "node_id"
#define NVS_KEY_CLAIMED "claimed"
#define NVS_KEY_HUB_ID "hub_id"
#define NVS_KEY_SHORT_ADDR "short_addr"

void node_identity_init(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        /* Standard ESP-IDF recovery pattern for a corrupt/version-mismatched
         * NVS partition: erase and retry once. */
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

bool node_identity_is_claimed(void) {
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle));
    uint8_t claimed = 0;
    esp_err_t err = nvs_get_u8(handle, NVS_KEY_CLAIMED, &claimed);
    if (err != ESP_ERR_NVS_NOT_FOUND) {
        ESP_ERROR_CHECK(err);
    }
    nvs_close(handle);
    return claimed != 0;
}

void node_identity_set_claimed(uint16_t hub_id, uint16_t short_address) {
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle));
    ESP_ERROR_CHECK(nvs_set_u8(handle, NVS_KEY_CLAIMED, 1));
    ESP_ERROR_CHECK(nvs_set_u16(handle, NVS_KEY_HUB_ID, hub_id));
    ESP_ERROR_CHECK(nvs_set_u16(handle, NVS_KEY_SHORT_ADDR, short_address));
    ESP_ERROR_CHECK(nvs_commit(handle));
    nvs_close(handle);
    ESP_LOGI(TAG, "claimed: hub_id=0x%04x short_address=0x%04x", hub_id, short_address);
}

uint16_t node_identity_get_hub_id(void) {
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle));
    uint16_t hub_id = 0;
    esp_err_t err = nvs_get_u16(handle, NVS_KEY_HUB_ID, &hub_id);
    if (err != ESP_ERR_NVS_NOT_FOUND) {
        ESP_ERROR_CHECK(err);
    }
    nvs_close(handle);
    return hub_id;
}

uint16_t node_identity_get_short_address(void) {
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle));
    uint16_t short_address = 0;
    esp_err_t err = nvs_get_u16(handle, NVS_KEY_SHORT_ADDR, &short_address);
    if (err != ESP_ERR_NVS_NOT_FOUND) {
        ESP_ERROR_CHECK(err);
    }
    nvs_close(handle);
    return short_address;
}

void node_identity_factory_reset(void) {
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle));
    ESP_ERROR_CHECK(nvs_erase_all(handle));
    ESP_ERROR_CHECK(nvs_commit(handle));
    nvs_close(handle);
    ESP_LOGI(TAG, "factory reset: claim state cleared");
}
