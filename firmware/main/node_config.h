#ifndef NODE_CONFIG_H
#define NODE_CONFIG_H

#include <stdint.h>

/* Bench-test default, same value as M1's TEST_WAKE_INTERVAL_SEC. The real
 * production interval (spec Section 4.1: ~1-2x/day) is expected to arrive
 * via a CONFIG push once the hub has a real value to send, not hardcoded
 * here. */
#define NODE_CONFIG_DEFAULT_WAKE_INTERVAL_SEC 30U

/* Same placeholder as M1 Task 4/6 pending real dry/wet calibration. */
#define NODE_CONFIG_DEFAULT_MOISTURE_DRY_THRESHOLD_RAW 2000U

/* Persisted via NVS (same partition node_identity.c uses, different
 * namespace) so a pushed config survives deep sleep and power loss, not
 * just the current wake cycle. */
uint32_t node_config_get_wake_interval_sec(void);
uint16_t node_config_get_moisture_dry_threshold_raw(void);
void node_config_apply(uint32_t wake_interval_sec, uint16_t moisture_dry_threshold_raw);

#endif
