#include "node_config.h"
#include <inttypes.h>
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"

static const char *TAG = "node_config";

#define NVS_NAMESPACE "node_cfg"
#define NVS_KEY_WAKE_INTERVAL "wake_ivl"
#define NVS_KEY_MOISTURE_THRESH "moist_thr"

uint32_t node_config_get_wake_interval_sec(void) {
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle));
    uint32_t value = NODE_CONFIG_DEFAULT_WAKE_INTERVAL_SEC;
    esp_err_t err = nvs_get_u32(handle, NVS_KEY_WAKE_INTERVAL, &value);
    if (err != ESP_ERR_NVS_NOT_FOUND) {
        ESP_ERROR_CHECK(err);
    }
    nvs_close(handle);
    return value;
}

uint16_t node_config_get_moisture_dry_threshold_raw(void) {
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle));
    uint16_t value = NODE_CONFIG_DEFAULT_MOISTURE_DRY_THRESHOLD_RAW;
    esp_err_t err = nvs_get_u16(handle, NVS_KEY_MOISTURE_THRESH, &value);
    if (err != ESP_ERR_NVS_NOT_FOUND) {
        ESP_ERROR_CHECK(err);
    }
    nvs_close(handle);
    return value;
}

void node_config_apply(uint32_t wake_interval_sec, uint16_t moisture_dry_threshold_raw) {
    nvs_handle_t handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle));
    ESP_ERROR_CHECK(nvs_set_u32(handle, NVS_KEY_WAKE_INTERVAL, wake_interval_sec));
    ESP_ERROR_CHECK(nvs_set_u16(handle, NVS_KEY_MOISTURE_THRESH, moisture_dry_threshold_raw));
    ESP_ERROR_CHECK(nvs_commit(handle));
    nvs_close(handle);
    ESP_LOGI(TAG, "config applied: wake_interval_sec=%" PRIu32 " moisture_dry_threshold_raw=%u",
             wake_interval_sec, (unsigned)moisture_dry_threshold_raw);
}
