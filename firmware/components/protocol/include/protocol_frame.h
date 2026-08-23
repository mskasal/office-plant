#ifndef PROTOCOL_FRAME_H
#define PROTOCOL_FRAME_H

#include <stdint.h>
#include <stddef.h>

#define FRAME_TYPE_BEACON   0x01
#define FRAME_TYPE_JOIN     0x02
#define FRAME_TYPE_DATA     0x03
#define FRAME_TYPE_BLINK    0x04
#define FRAME_TYPE_CLAIM    0x05
#define FRAME_TYPE_ANNOUNCE 0x06
#define FRAME_TYPE_CONFIG   0x07

#define BEACON_FRAME_LEN 4
#define JOIN_FRAME_LEN   5
#define DATA_FRAME_LEN   9
/* BLINK/CLAIM reuse JOIN's wire shape exactly (type + 2x uint16 fields),
 * per the M4 plan's "New frame types, reusing the existing 5-byte addr-pair
 * shape" decision — only the field semantics differ, not the byte layout. */
#define BLINK_FRAME_LEN JOIN_FRAME_LEN
#define CLAIM_FRAME_LEN JOIN_FRAME_LEN
/* ANNOUNCE is new, not in the M4 plan's task list: an unclaimed node in
 * pairing mode needs to periodically advertise itself (factory_id) so the
 * hub can discover it at all — BLINK/CLAIM alone are hub-initiated and
 * require already knowing which node to target. Without something like
 * this, "Discovery filtering — hub-side, not firmware-side" (the plan's
 * own wording) has nothing to filter. See firmware/main/pairing_mode.c. */
#define ANNOUNCE_FRAME_LEN 3
/* CONFIG is new, not in any prior milestone's task list: spec Section 4.1
 * commits to "the hub is in charge of schedule/config... the response
 * piggybacks any updated config" as core v1 protocol behavior, but nothing
 * through M4 implemented a frame for it. M5's own validation checklist
 * requires testing exactly this ("push a config change from the hub...
 * confirm a node picks it up on its next check-in"), so it has to exist
 * before that checklist is even runnable. type(1) + target_node_id(2) +
 * wake_interval_sec(4) + moisture_dry_threshold_raw(2) = 9 bytes, same as
 * DATA_FRAME_LEN — no change needed to PROTOCOL_FRAME_MAX_LEN. */
#define CONFIG_FRAME_LEN 9
#define PROTOCOL_FRAME_MAX_LEN DATA_FRAME_LEN

typedef struct {
    uint16_t sender_id;
    uint8_t hop_count;
} beacon_frame_t;

typedef struct {
    uint16_t sender_id;
    uint16_t target_parent_id;
} join_frame_t;

typedef enum {
    NEEDS_WATER_FALSE = 0,
    NEEDS_WATER_TRUE = 1,
    NEEDS_WATER_NONE = 2,
} needs_water_t;

typedef struct {
    uint16_t sender_id;
    needs_water_t needs_water;
    uint8_t battery_pct;
    uint32_t timestamp;
} data_frame_t;

/* hub -> node: node whose factory_id == target_node_id blinks its LED. */
typedef struct {
    uint16_t hub_id;
    uint16_t target_node_id;
} blink_frame_t;

/* hub -> node: every unclaimed node hearing this persists hub_id +
 * assigned_short_address and leaves pairing mode. Has no per-node
 * targeting field (see firmware/main/pairing_mode.c's handle_frame for why
 * that's safe within this milestone's scope). */
typedef struct {
    uint16_t assigned_short_address;
    uint16_t hub_id;
} claim_frame_t;

/* node -> hub: an unclaimed node's periodic pairing-mode presence signal. */
typedef struct {
    uint16_t factory_id;
} announce_frame_t;

/* hub -> node: piggybacked on a DATA frame's response window (spec Section
 * 4.1). target_node_id lets the hub address one node on a shared/
 * promiscuous channel where multiple claimed nodes' listen windows could
 * otherwise overlap. */
typedef struct {
    uint16_t target_node_id;
    uint32_t wake_interval_sec;
    uint16_t moisture_dry_threshold_raw;
} config_frame_t;

size_t encode_beacon_frame(const beacon_frame_t *in, uint8_t *out_buf);
size_t encode_join_frame(const join_frame_t *in, uint8_t *out_buf);
size_t encode_data_frame(const data_frame_t *in, uint8_t *out_buf);
size_t encode_blink_frame(const blink_frame_t *in, uint8_t *out_buf);
size_t encode_claim_frame(const claim_frame_t *in, uint8_t *out_buf);
size_t encode_announce_frame(const announce_frame_t *in, uint8_t *out_buf);
size_t encode_config_frame(const config_frame_t *in, uint8_t *out_buf);

int decode_frame_type(const uint8_t *buf, size_t len);
int decode_beacon_frame(const uint8_t *buf, size_t len, beacon_frame_t *out);
int decode_join_frame(const uint8_t *buf, size_t len, join_frame_t *out);
int decode_data_frame(const uint8_t *buf, size_t len, data_frame_t *out);
int decode_blink_frame(const uint8_t *buf, size_t len, blink_frame_t *out);
int decode_claim_frame(const uint8_t *buf, size_t len, claim_frame_t *out);
int decode_announce_frame(const uint8_t *buf, size_t len, announce_frame_t *out);
int decode_config_frame(const uint8_t *buf, size_t len, config_frame_t *out);

#endif
