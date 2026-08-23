#include "moisture_sensor.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_err.h"
#include "esp_log.h"

static const char *TAG = "moisture_sensor";
static adc_oneshot_unit_handle_t s_adc_handle = NULL;

void moisture_sensor_init(void) {
    adc_oneshot_unit_init_cfg_t init_config = {
        .unit_id = ADC_UNIT_1,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&init_config, &s_adc_handle));

    adc_oneshot_chan_cfg_t chan_config = {
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .atten = ADC_ATTEN_DB_12,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(s_adc_handle, MOISTURE_SENSOR_ADC_CHANNEL, &chan_config));
}

int moisture_sensor_read_raw(void) {
    int raw = 0;
    ESP_ERROR_CHECK(adc_oneshot_read(s_adc_handle, MOISTURE_SENSOR_ADC_CHANNEL, &raw));
    ESP_LOGI(TAG, "raw ADC reading: %d", raw);
    return raw;
}

void moisture_sensor_deinit(void) {
    adc_oneshot_del_unit(s_adc_handle);
    s_adc_handle = NULL;
}
