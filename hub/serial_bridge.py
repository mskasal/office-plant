"""Dongle<->Pi serial protocol (M3 plan, "Decision: dongle <-> Pi serial
protocol"): a simple line-based, human-debuggable framing with no binary
checksum/framing library.

Dongle -> Pi, one line per received mesh frame:  "RX <hex> <rssi>\\n"
Pi -> Dongle, one line per outbound command:      "TX <hex>\\n"

`SerialBridge` is deliberately decoupled from any specific serial library:
`port` only needs pyserial's readline()/write() shape, so tests can
substitute a fake in-memory port without real hardware.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Union

from hub.protocol_frame import (
    FRAME_TYPE_ANNOUNCE,
    FRAME_TYPE_BEACON,
    FRAME_TYPE_BLINK,
    FRAME_TYPE_CLAIM,
    FRAME_TYPE_CONFIG,
    FRAME_TYPE_DATA,
    FRAME_TYPE_JOIN,
    AnnounceFrame,
    BeaconFrame,
    BlinkFrame,
    ClaimFrame,
    ConfigFrame,
    DataFrame,
    JoinFrame,
    decode_announce_frame,
    decode_beacon_frame,
    decode_blink_frame,
    decode_claim_frame,
    decode_config_frame,
    decode_data_frame,
    decode_frame_type,
    decode_join_frame,
)

Frame = Union[BeaconFrame, JoinFrame, DataFrame, BlinkFrame, ClaimFrame, AnnounceFrame, ConfigFrame]


@dataclass
class ReceivedFrame:
    frame: Frame
    rssi: int


class SerialPort(Protocol):
    def readline(self) -> bytes: ...
    def write(self, data: bytes) -> int: ...


_DECODERS = {
    FRAME_TYPE_BEACON: decode_beacon_frame,
    FRAME_TYPE_JOIN: decode_join_frame,
    FRAME_TYPE_DATA: decode_data_frame,
    FRAME_TYPE_BLINK: decode_blink_frame,
    FRAME_TYPE_CLAIM: decode_claim_frame,
    FRAME_TYPE_ANNOUNCE: decode_announce_frame,
    FRAME_TYPE_CONFIG: decode_config_frame,
}


def decode_rx_line(line: str) -> Optional[ReceivedFrame]:
    """Parses one dongle->Pi "RX <hex> <rssi>" line. Returns None for a
    malformed line, unknown hex, or a payload that fails to decode as any
    known frame type — the hub logs and drops these rather than crashing on
    a corrupted/partial serial read."""
    parts = line.strip().split()
    if len(parts) != 3 or parts[0] != "RX":
        return None

    try:
        payload = bytes.fromhex(parts[1])
        rssi = int(parts[2])
    except ValueError:
        return None

    frame_type = decode_frame_type(payload)
    decoder = _DECODERS.get(frame_type) if frame_type is not None else None
    if decoder is None:
        return None

    frame = decoder(payload)
    if frame is None:
        return None
    return ReceivedFrame(frame=frame, rssi=rssi)


def encode_tx_line(payload: bytes) -> str:
    return f"TX {payload.hex()}\n"


class SerialBridge:
    """Reads RX lines from the dongle's serial port and dispatches decoded
    frames to `on_frame`; sends TX lines back out via `send`."""

    def __init__(self, port: SerialPort, on_frame: Callable[[ReceivedFrame], None]):
        self.port = port
        self.on_frame = on_frame

    def poll_once(self) -> bool:
        """Reads and processes a single line. Returns True if a frame was
        decoded and dispatched, False for a blank/malformed line or EOF."""
        raw = self.port.readline()
        if not raw:
            return False
        line = raw.decode("ascii", errors="ignore")
        received = decode_rx_line(line)
        if received is None:
            return False
        self.on_frame(received)
        return True

    def send(self, payload: bytes) -> None:
        self.port.write(encode_tx_line(payload).encode("ascii"))
