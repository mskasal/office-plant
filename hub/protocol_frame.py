"""Python port of firmware/components/protocol/protocol_frame.c.

Must stay byte-for-byte consistent with the C version: any change to one
requires the same change in the other (see the M3 plan's Task 2 note). The
frame-type constants, field order, field widths, and little-endian encoding
below are a direct mirror of protocol_frame.h/.c.

The C API returns an int status code through an out-param; here decode
returns the frame dataclass directly, or None on a type/length mismatch —
the byte layout is what must match, not the calling convention.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Union

FRAME_TYPE_BEACON = 0x01
FRAME_TYPE_JOIN = 0x02
FRAME_TYPE_DATA = 0x03
FRAME_TYPE_BLINK = 0x04
FRAME_TYPE_CLAIM = 0x05
FRAME_TYPE_ANNOUNCE = 0x06
FRAME_TYPE_CONFIG = 0x07

BEACON_FRAME_LEN = 4
JOIN_FRAME_LEN = 5
DATA_FRAME_LEN = 9
# BLINK/CLAIM reuse JOIN's wire shape exactly (type + 2x uint16), per the M4
# plan's "reusing the existing 5-byte addr-pair shape" decision.
BLINK_FRAME_LEN = JOIN_FRAME_LEN
CLAIM_FRAME_LEN = JOIN_FRAME_LEN
# ANNOUNCE is new, not in the M4 plan's task list: an unclaimed node needs to
# periodically advertise itself so the hub can discover it at all (BLINK/
# CLAIM are hub-initiated and require already knowing which node to target).
# See firmware/components/protocol/include/protocol_frame.h's matching note.
ANNOUNCE_FRAME_LEN = 3
# CONFIG is new, not in any prior milestone's task list: spec Section 4.1
# commits to config being piggybacked on a node's DATA response window as
# core v1 behavior, but nothing through M4 implemented a frame for it. See
# protocol_frame.h's matching note for why M5 needs this to exist at all.
CONFIG_FRAME_LEN = 9
PROTOCOL_FRAME_MAX_LEN = DATA_FRAME_LEN


class NeedsWater(IntEnum):
    FALSE = 0
    TRUE = 1
    NONE = 2


@dataclass
class BeaconFrame:
    sender_id: int
    hop_count: int


@dataclass
class JoinFrame:
    sender_id: int
    target_parent_id: int


@dataclass
class DataFrame:
    sender_id: int
    needs_water: NeedsWater
    battery_pct: int
    timestamp: int


@dataclass
class BlinkFrame:
    hub_id: int
    target_node_id: int


@dataclass
class ClaimFrame:
    assigned_short_address: int
    hub_id: int


@dataclass
class AnnounceFrame:
    factory_id: int


@dataclass
class ConfigFrame:
    target_node_id: int
    wake_interval_sec: int
    moisture_dry_threshold_raw: int


Frame = Union[BeaconFrame, JoinFrame, DataFrame, BlinkFrame, ClaimFrame, AnnounceFrame, ConfigFrame]


def encode_beacon_frame(frame: BeaconFrame) -> bytes:
    return (
        bytes([FRAME_TYPE_BEACON])
        + frame.sender_id.to_bytes(2, "little")
        + bytes([frame.hop_count])
    )


def encode_join_frame(frame: JoinFrame) -> bytes:
    return (
        bytes([FRAME_TYPE_JOIN])
        + frame.sender_id.to_bytes(2, "little")
        + frame.target_parent_id.to_bytes(2, "little")
    )


def encode_data_frame(frame: DataFrame) -> bytes:
    return (
        bytes([FRAME_TYPE_DATA])
        + frame.sender_id.to_bytes(2, "little")
        + bytes([int(frame.needs_water)])
        + bytes([frame.battery_pct])
        + frame.timestamp.to_bytes(4, "little")
    )


def encode_blink_frame(frame: BlinkFrame) -> bytes:
    return (
        bytes([FRAME_TYPE_BLINK])
        + frame.hub_id.to_bytes(2, "little")
        + frame.target_node_id.to_bytes(2, "little")
    )


def encode_claim_frame(frame: ClaimFrame) -> bytes:
    return (
        bytes([FRAME_TYPE_CLAIM])
        + frame.assigned_short_address.to_bytes(2, "little")
        + frame.hub_id.to_bytes(2, "little")
    )


def encode_announce_frame(frame: AnnounceFrame) -> bytes:
    return bytes([FRAME_TYPE_ANNOUNCE]) + frame.factory_id.to_bytes(2, "little")


def encode_config_frame(frame: ConfigFrame) -> bytes:
    return (
        bytes([FRAME_TYPE_CONFIG])
        + frame.target_node_id.to_bytes(2, "little")
        + frame.wake_interval_sec.to_bytes(4, "little")
        + frame.moisture_dry_threshold_raw.to_bytes(2, "little")
    )


def decode_frame_type(buf: bytes) -> Optional[int]:
    if len(buf) == 0:
        return None
    return buf[0]


def decode_beacon_frame(buf: bytes) -> Optional[BeaconFrame]:
    if len(buf) != BEACON_FRAME_LEN or buf[0] != FRAME_TYPE_BEACON:
        return None
    return BeaconFrame(
        sender_id=int.from_bytes(buf[1:3], "little"),
        hop_count=buf[3],
    )


def decode_join_frame(buf: bytes) -> Optional[JoinFrame]:
    if len(buf) != JOIN_FRAME_LEN or buf[0] != FRAME_TYPE_JOIN:
        return None
    return JoinFrame(
        sender_id=int.from_bytes(buf[1:3], "little"),
        target_parent_id=int.from_bytes(buf[3:5], "little"),
    )


def decode_data_frame(buf: bytes) -> Optional[DataFrame]:
    if len(buf) != DATA_FRAME_LEN or buf[0] != FRAME_TYPE_DATA:
        return None
    return DataFrame(
        sender_id=int.from_bytes(buf[1:3], "little"),
        needs_water=NeedsWater(buf[3]),
        battery_pct=buf[4],
        timestamp=int.from_bytes(buf[5:9], "little"),
    )


def decode_blink_frame(buf: bytes) -> Optional[BlinkFrame]:
    if len(buf) != BLINK_FRAME_LEN or buf[0] != FRAME_TYPE_BLINK:
        return None
    return BlinkFrame(
        hub_id=int.from_bytes(buf[1:3], "little"),
        target_node_id=int.from_bytes(buf[3:5], "little"),
    )


def decode_claim_frame(buf: bytes) -> Optional[ClaimFrame]:
    if len(buf) != CLAIM_FRAME_LEN or buf[0] != FRAME_TYPE_CLAIM:
        return None
    return ClaimFrame(
        assigned_short_address=int.from_bytes(buf[1:3], "little"),
        hub_id=int.from_bytes(buf[3:5], "little"),
    )


def decode_announce_frame(buf: bytes) -> Optional[AnnounceFrame]:
    if len(buf) != ANNOUNCE_FRAME_LEN or buf[0] != FRAME_TYPE_ANNOUNCE:
        return None
    return AnnounceFrame(factory_id=int.from_bytes(buf[1:3], "little"))


def decode_config_frame(buf: bytes) -> Optional[ConfigFrame]:
    if len(buf) != CONFIG_FRAME_LEN or buf[0] != FRAME_TYPE_CONFIG:
        return None
    return ConfigFrame(
        target_node_id=int.from_bytes(buf[1:3], "little"),
        wake_interval_sec=int.from_bytes(buf[3:7], "little"),
        moisture_dry_threshold_raw=int.from_bytes(buf[7:9], "little"),
    )
