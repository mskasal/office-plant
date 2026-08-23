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

size_t encode_blink_frame(const blink_frame_t *in, uint8_t *out_buf) {
    out_buf[0] = FRAME_TYPE_BLINK;
    write_u16le(out_buf + 1, in->hub_id);
    write_u16le(out_buf + 3, in->target_node_id);
    return BLINK_FRAME_LEN;
}

size_t encode_claim_frame(const claim_frame_t *in, uint8_t *out_buf) {
    out_buf[0] = FRAME_TYPE_CLAIM;
    write_u16le(out_buf + 1, in->assigned_short_address);
    write_u16le(out_buf + 3, in->hub_id);
    return CLAIM_FRAME_LEN;
}

size_t encode_announce_frame(const announce_frame_t *in, uint8_t *out_buf) {
    out_buf[0] = FRAME_TYPE_ANNOUNCE;
    write_u16le(out_buf + 1, in->factory_id);
    return ANNOUNCE_FRAME_LEN;
}

size_t encode_config_frame(const config_frame_t *in, uint8_t *out_buf) {
    out_buf[0] = FRAME_TYPE_CONFIG;
    write_u16le(out_buf + 1, in->target_node_id);
    write_u32le(out_buf + 3, in->wake_interval_sec);
    write_u16le(out_buf + 7, in->moisture_dry_threshold_raw);
    return CONFIG_FRAME_LEN;
}

int decode_blink_frame(const uint8_t *buf, size_t len, blink_frame_t *out) {
    if (len != BLINK_FRAME_LEN || buf[0] != FRAME_TYPE_BLINK) {
        return -1;
    }
    out->hub_id = read_u16le(buf + 1);
    out->target_node_id = read_u16le(buf + 3);
    return 0;
}

int decode_claim_frame(const uint8_t *buf, size_t len, claim_frame_t *out) {
    if (len != CLAIM_FRAME_LEN || buf[0] != FRAME_TYPE_CLAIM) {
        return -1;
    }
    out->assigned_short_address = read_u16le(buf + 1);
    out->hub_id = read_u16le(buf + 3);
    return 0;
}

int decode_announce_frame(const uint8_t *buf, size_t len, announce_frame_t *out) {
    if (len != ANNOUNCE_FRAME_LEN || buf[0] != FRAME_TYPE_ANNOUNCE) {
        return -1;
    }
    out->factory_id = read_u16le(buf + 1);
    return 0;
}

int decode_config_frame(const uint8_t *buf, size_t len, config_frame_t *out) {
    if (len != CONFIG_FRAME_LEN || buf[0] != FRAME_TYPE_CONFIG) {
        return -1;
    }
    out->target_node_id = read_u16le(buf + 1);
    out->wake_interval_sec = read_u32le(buf + 3);
    out->moisture_dry_threshold_raw = read_u16le(buf + 7);
    return 0;
}
