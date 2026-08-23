#include "factory_reset_button.h"
#include <inttypes.h>
#include "driver/gpio.h"
#include "esp_sleep.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "factory_reset_button";

/* Reuses the ESP32-C6 dev board's existing BOOT button (commonly GPIO9)
 * rather than adding a dedicated button to the BOM, per the M4 plan's
 * cost-driven "Factory reset — hardware button" decision. Confirm against
 * the specific board's schematic — same caveat status as M1's ADC GPIO
 * note (developer-setup.md Section 6). */
#define FACTORY_RESET_BUTTON_GPIO GPIO_NUM_9

#define FACTORY_RESET_HOLD_MS 5000
#define FACTORY_RESET_POLL_INTERVAL_MS 100

/* BOOT button is active-low (pressed = GPIO reads 0) on Espressif dev
 * boards. */
static bool button_is_pressed(void) {
    return gpio_get_level(FACTORY_RESET_BUTTON_GPIO) == 0;
}

void factory_reset_button_enable_wakeup(void) {
    gpio_set_direction(FACTORY_RESET_BUTTON_GPIO, GPIO_MODE_INPUT);
    gpio_pullup_en(FACTORY_RESET_BUTTON_GPIO);
    ESP_ERROR_CHECK(esp_sleep_enable_ext1_wakeup(1ULL << FACTORY_RESET_BUTTON_GPIO, ESP_EXT1_WAKEUP_ANY_LOW));
}

bool factory_reset_button_caused_wakeup(void) {
    return esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT1;
}

bool factory_reset_button_confirm_long_press(void) {
    TickType_t start = xTaskGetTickCount();
    while (button_is_pressed()) {
        uint32_t held_ms = (xTaskGetTickCount() - start) * portTICK_PERIOD_MS;
        if (held_ms >= FACTORY_RESET_HOLD_MS) {
            ESP_LOGI(TAG, "factory-reset button held for %" PRIu32 " ms — confirmed", held_ms);
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(FACTORY_RESET_POLL_INTERVAL_MS));
    }
    ESP_LOGI(TAG, "factory-reset button released early — ignoring");
    return false;
}
