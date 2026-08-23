from hub.protocol_frame import (
    ANNOUNCE_FRAME_LEN,
    BEACON_FRAME_LEN,
    BLINK_FRAME_LEN,
    CLAIM_FRAME_LEN,
    CONFIG_FRAME_LEN,
    DATA_FRAME_LEN,
    FRAME_TYPE_ANNOUNCE,
    FRAME_TYPE_BEACON,
    FRAME_TYPE_BLINK,
    FRAME_TYPE_CLAIM,
    FRAME_TYPE_CONFIG,
    FRAME_TYPE_DATA,
    JOIN_FRAME_LEN,
    PROTOCOL_FRAME_MAX_LEN,
    AnnounceFrame,
    BeaconFrame,
    BlinkFrame,
    ClaimFrame,
    ConfigFrame,
    DataFrame,
    JoinFrame,
    NeedsWater,
    decode_announce_frame,
    decode_beacon_frame,
    decode_blink_frame,
    decode_claim_frame,
    decode_config_frame,
    decode_data_frame,
    decode_frame_type,
    decode_join_frame,
    encode_announce_frame,
    encode_beacon_frame,
    encode_blink_frame,
    encode_claim_frame,
    encode_config_frame,
    encode_data_frame,
    encode_join_frame,
)


def test_beacon_roundtrip():
    frame = BeaconFrame(sender_id=42, hop_count=3)
    buf = encode_beacon_frame(frame)
    assert len(buf) == BEACON_FRAME_LEN
    assert decode_frame_type(buf) == FRAME_TYPE_BEACON

    out = decode_beacon_frame(buf)
    assert out == frame


def test_join_roundtrip():
    frame = JoinFrame(sender_id=1000, target_parent_id=7)
    buf = encode_join_frame(frame)
    assert len(buf) == JOIN_FRAME_LEN

    out = decode_join_frame(buf)
    assert out == frame


def test_data_roundtrip():
    frame = DataFrame(sender_id=65535, needs_water=NeedsWater.TRUE, battery_pct=87, timestamp=0x01020304)
    buf = encode_data_frame(frame)
    assert len(buf) == DATA_FRAME_LEN

    out = decode_data_frame(buf)
    assert out == frame


def test_blink_roundtrip():
    frame = BlinkFrame(hub_id=0, target_node_id=0xBEEF)
    buf = encode_blink_frame(frame)
    assert len(buf) == BLINK_FRAME_LEN
    assert decode_frame_type(buf) == FRAME_TYPE_BLINK

    out = decode_blink_frame(buf)
    assert out == frame


def test_claim_roundtrip():
    frame = ClaimFrame(assigned_short_address=12, hub_id=0)
    buf = encode_claim_frame(frame)
    assert len(buf) == CLAIM_FRAME_LEN

    out = decode_claim_frame(buf)
    assert out == frame


def test_announce_roundtrip():
    frame = AnnounceFrame(factory_id=0xABCD)
    buf = encode_announce_frame(frame)
    assert len(buf) == ANNOUNCE_FRAME_LEN
    assert decode_frame_type(buf) == FRAME_TYPE_ANNOUNCE

    out = decode_announce_frame(buf)
    assert out == frame


def test_config_roundtrip():
    frame = ConfigFrame(target_node_id=7, wake_interval_sec=43200, moisture_dry_threshold_raw=1800)
    buf = encode_config_frame(frame)
    assert len(buf) == CONFIG_FRAME_LEN
    assert decode_frame_type(buf) == FRAME_TYPE_CONFIG

    out = decode_config_frame(buf)
    assert out == frame


def test_wrong_type_rejected():
    buf = encode_beacon_frame(BeaconFrame(sender_id=1, hop_count=0))
    assert decode_data_frame(buf) is None


def test_wrong_length_rejected():
    buf = bytes([FRAME_TYPE_DATA, 0, 0, 0])
    assert decode_data_frame(buf) is None


def test_max_len_fits_all_frame_types():
    assert PROTOCOL_FRAME_MAX_LEN >= BEACON_FRAME_LEN
    assert PROTOCOL_FRAME_MAX_LEN >= JOIN_FRAME_LEN
    assert PROTOCOL_FRAME_MAX_LEN >= DATA_FRAME_LEN
    assert PROTOCOL_FRAME_MAX_LEN >= BLINK_FRAME_LEN
    assert PROTOCOL_FRAME_MAX_LEN >= CLAIM_FRAME_LEN
    assert PROTOCOL_FRAME_MAX_LEN >= ANNOUNCE_FRAME_LEN
    assert PROTOCOL_FRAME_MAX_LEN >= CONFIG_FRAME_LEN
    # 802.15.4 aMaxPHYPacketSize is 127 bytes, including the 2-byte
    # hardware-appended FCS and our own header.
    assert PROTOCOL_FRAME_MAX_LEN < 127 - 2


def test_data_frame_byte_layout_matches_c_encoding():
    """Cross-checks the exact wire bytes against the C encoder's known
    output for the same inputs (firmware/components/protocol/protocol_frame.c),
    since the plan requires byte-for-byte consistency between the two ports."""
    frame = DataFrame(sender_id=65535, needs_water=NeedsWater.TRUE, battery_pct=87, timestamp=0x01020304)
    buf = encode_data_frame(frame)
    assert buf == bytes([
        FRAME_TYPE_DATA,
        0xFF, 0xFF,  # sender_id = 65535, little-endian
        0x01,        # needs_water = NEEDS_WATER_TRUE
        87,          # battery_pct
        0x04, 0x03, 0x02, 0x01,  # timestamp = 0x01020304, little-endian
    ])


def test_claim_frame_byte_layout_matches_c_encoding():
    """Same cross-check as above, for the M4-added CLAIM frame — the field
    order (assigned_short_address, hub_id) differs from JOIN's (sender_id,
    target_parent_id) despite sharing the same wire shape/length."""
    frame = ClaimFrame(assigned_short_address=12, hub_id=0)
    buf = encode_claim_frame(frame)
    assert buf == bytes([
        FRAME_TYPE_CLAIM,
        12, 0,  # assigned_short_address = 12, little-endian
        0, 0,   # hub_id = 0, little-endian
    ])
