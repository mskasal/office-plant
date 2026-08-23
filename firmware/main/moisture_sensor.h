#ifndef MOISTURE_SENSOR_H
#define MOISTURE_SENSOR_H

#include "hal/adc_types.h"

/* ADC1 channel 0 is GPIO0 on ESP32-C6 (confirmed against
 * soc/esp32c6/include/soc/adc_channel.h). */
#define MOISTURE_SENSOR_ADC_CHANNEL ADC_CHANNEL_0

void moisture_sensor_init(void);
int moisture_sensor_read_raw(void);
void moisture_sensor_deinit(void);

#endif
