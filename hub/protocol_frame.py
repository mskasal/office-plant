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

BEACON_FRAME_LEN = 4
JOIN_FRAME_LEN = 5
DATA_FRAME_LEN = 9
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


Frame = Union[BeaconFrame, JoinFrame, DataFrame]


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
