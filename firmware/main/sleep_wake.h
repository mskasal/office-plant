#ifndef SLEEP_WAKE_H
#define SLEEP_WAKE_H

#include <stdint.h>

void sleep_wake_log_boot(void);
void sleep_wake_go_to_sleep(uint32_t seconds);

#endif
