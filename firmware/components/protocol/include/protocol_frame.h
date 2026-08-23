#ifndef PROTOCOL_FRAME_H
#define PROTOCOL_FRAME_H

#include <stdint.h>
#include <stddef.h>

#define FRAME_TYPE_BEACON 0x01
#define FRAME_TYPE_JOIN   0x02
#define FRAME_TYPE_DATA   0x03

#define BEACON_FRAME_LEN 4
#define JOIN_FRAME_LEN   5
#define DATA_FRAME_LEN   9
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

size_t encode_beacon_frame(const beacon_frame_t *in, uint8_t *out_buf);
size_t encode_join_frame(const join_frame_t *in, uint8_t *out_buf);
size_t encode_data_frame(const data_frame_t *in, uint8_t *out_buf);

int decode_frame_type(const uint8_t *buf, size_t len);
int decode_beacon_frame(const uint8_t *buf, size_t len, beacon_frame_t *out);
int decode_join_frame(const uint8_t *buf, size_t len, join_frame_t *out);
int decode_data_frame(const uint8_t *buf, size_t len, data_frame_t *out);

#endif
