#include "protocol_frame.h"

static void write_u16le(uint8_t *buf, uint16_t v) {
    buf[0] = (uint8_t)(v & 0xFF);
    buf[1] = (uint8_t)((v >> 8) & 0xFF);
}

static uint16_t read_u16le(const uint8_t *buf) {
    return (uint16_t)(buf[0] | ((uint16_t)buf[1] << 8));
}

static void write_u32le(uint8_t *buf, uint32_t v) {
    buf[0] = (uint8_t)(v & 0xFF);
    buf[1] = (uint8_t)((v >> 8) & 0xFF);
    buf[2] = (uint8_t)((v >> 16) & 0xFF);
    buf[3] = (uint8_t)((v >> 24) & 0xFF);
}

static uint32_t read_u32le(const uint8_t *buf) {
    return (uint32_t)buf[0] | ((uint32_t)buf[1] << 8) |
           ((uint32_t)buf[2] << 16) | ((uint32_t)buf[3] << 24);
}

size_t encode_beacon_frame(const beacon_frame_t *in, uint8_t *out_buf) {
    out_buf[0] = FRAME_TYPE_BEACON;
    write_u16le(out_buf + 1, in->sender_id);
    out_buf[3] = in->hop_count;
    return BEACON_FRAME_LEN;
}

size_t encode_join_frame(const join_frame_t *in, uint8_t *out_buf) {
    out_buf[0] = FRAME_TYPE_JOIN;
    write_u16le(out_buf + 1, in->sender_id);
    write_u16le(out_buf + 3, in->target_parent_id);
    return JOIN_FRAME_LEN;
}

size_t encode_data_frame(const data_frame_t *in, uint8_t *out_buf) {
    out_buf[0] = FRAME_TYPE_DATA;
    write_u16le(out_buf + 1, in->sender_id);
    out_buf[3] = (uint8_t)in->needs_water;
    out_buf[4] = in->battery_pct;
    write_u32le(out_buf + 5, in->timestamp);
    return DATA_FRAME_LEN;
}

int decode_frame_type(const uint8_t *buf, size_t len) {
    if (len == 0) {
        return -1;
    }
    return buf[0];
}

int decode_beacon_frame(const uint8_t *buf, size_t len, beacon_frame_t *out) {
    if (len != BEACON_FRAME_LEN || buf[0] != FRAME_TYPE_BEACON) {
        return -1;
    }
    out->sender_id = read_u16le(buf + 1);
    out->hop_count = buf[3];
    return 0;
}

int decode_join_frame(const uint8_t *buf, size_t len, join_frame_t *out) {
    if (len != JOIN_FRAME_LEN || buf[0] != FRAME_TYPE_JOIN) {
        return -1;
    }
    out->sender_id = read_u16le(buf + 1);
    out->target_parent_id = read_u16le(buf + 3);
    return 0;
}

int decode_data_frame(const uint8_t *buf, size_t len, data_frame_t *out) {
    if (len != DATA_FRAME_LEN || buf[0] != FRAME_TYPE_DATA) {
        return -1;
    }
    out->sender_id = read_u16le(buf + 1);
    out->needs_water = (needs_water_t)buf[3];
    out->battery_pct = buf[4];
    out->timestamp = read_u32le(buf + 5);
    return 0;
}
