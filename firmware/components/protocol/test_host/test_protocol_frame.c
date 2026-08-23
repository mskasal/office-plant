#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "protocol_frame.h"

static int failures = 0;

#define CHECK(cond) do { \
    if (!(cond)) { \
        printf("FAIL: %s (line %d)\n", #cond, __LINE__); \
        failures++; \
    } \
} while (0)

static void test_beacon_roundtrip(void) {
    beacon_frame_t in = { .sender_id = 42, .hop_count = 3 };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t n = encode_beacon_frame(&in, buf);
    CHECK(n == BEACON_FRAME_LEN);
    CHECK(decode_frame_type(buf, n) == FRAME_TYPE_BEACON);

    beacon_frame_t out;
    CHECK(decode_beacon_frame(buf, n, &out) == 0);
    CHECK(out.sender_id == 42);
    CHECK(out.hop_count == 3);
}

static void test_join_roundtrip(void) {
    join_frame_t in = { .sender_id = 1000, .target_parent_id = 7 };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t n = encode_join_frame(&in, buf);
    CHECK(n == JOIN_FRAME_LEN);

    join_frame_t out;
    CHECK(decode_join_frame(buf, n, &out) == 0);
    CHECK(out.sender_id == 1000);
    CHECK(out.target_parent_id == 7);
}

static void test_data_roundtrip(void) {
    data_frame_t in = {
        .sender_id = 65535,
        .needs_water = NEEDS_WATER_TRUE,
        .battery_pct = 87,
        .timestamp = 0x01020304,
    };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t n = encode_data_frame(&in, buf);
    CHECK(n == DATA_FRAME_LEN);

    data_frame_t out;
    CHECK(decode_data_frame(buf, n, &out) == 0);
    CHECK(out.sender_id == 65535);
    CHECK(out.needs_water == NEEDS_WATER_TRUE);
    CHECK(out.battery_pct == 87);
    CHECK(out.timestamp == 0x01020304u);
}

static void test_wrong_type_rejected(void) {
    beacon_frame_t beacon_in = { .sender_id = 1, .hop_count = 0 };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t n = encode_beacon_frame(&beacon_in, buf);

    data_frame_t data_out;
    CHECK(decode_data_frame(buf, n, &data_out) == -1);
}

static void test_wrong_length_rejected(void) {
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN] = { FRAME_TYPE_DATA, 0, 0, 0 };
    data_frame_t out;
    CHECK(decode_data_frame(buf, 4, &out) == -1);
}

static void test_max_len_fits_all_frame_types(void) {
    CHECK(PROTOCOL_FRAME_MAX_LEN >= BEACON_FRAME_LEN);
    CHECK(PROTOCOL_FRAME_MAX_LEN >= JOIN_FRAME_LEN);
    CHECK(PROTOCOL_FRAME_MAX_LEN >= DATA_FRAME_LEN);
    /* 802.15.4 aMaxPHYPacketSize is 127 bytes, including the 2-byte
     * hardware-appended FCS and our own header; our largest frame must
     * leave comfortable headroom. */
    CHECK(PROTOCOL_FRAME_MAX_LEN < 127 - 2);
}

int main(void) {
    test_beacon_roundtrip();
    test_join_roundtrip();
    test_data_roundtrip();
    test_wrong_type_rejected();
    test_wrong_length_rejected();
    test_max_len_fits_all_frame_types();

    if (failures == 0) {
        printf("All tests passed.\n");
        return 0;
    }
    printf("%d check(s) failed.\n", failures);
    return 1;
}
