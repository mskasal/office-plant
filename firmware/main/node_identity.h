#ifndef NODE_IDENTITY_H
#define NODE_IDENTITY_H

#include <stdint.h>
#include <stdbool.h>

/* Must be called once at boot, before any other node_identity_* call.
 * Wraps nvs_flash_init(), including the standard erase-and-retry recovery
 * path ESP-IDF's own examples use for a corrupt/version-mismatched NVS
 * partition. */
void node_identity_init(void);

/* claimed/hub_id/short_address must survive a full power loss (battery
 * swap, not just deep sleep) — M1's RTC_DATA_ATTR does not survive that,
 * so this is backed by NVS instead (M4 plan's "Persistent node identity —
 * NVS, not RTC memory" decision). */
bool node_identity_is_claimed(void);

/* Persists hub_id + short_address to NVS and marks the node claimed. */
void node_identity_set_claimed(uint16_t hub_id, uint16_t short_address);

/* 0 if never claimed. */
uint16_t node_identity_get_hub_id(void);
uint16_t node_identity_get_short_address(void);

/* Clears claim state in NVS. Caller is responsible for rebooting into
 * pairing mode afterward (M4 plan: "5s hold -> factory_reset() -> reboot
 * into pairing mode"). */
void node_identity_factory_reset(void);

#endif
