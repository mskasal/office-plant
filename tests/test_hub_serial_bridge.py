from hub.protocol_frame import (
    AnnounceFrame,
    BeaconFrame,
    DataFrame,
    NeedsWater,
    encode_announce_frame,
    encode_beacon_frame,
    encode_data_frame,
)
from hub.serial_bridge import SerialBridge, decode_rx_line, encode_tx_line


class FakeSerialPort:
    """Feeds canned RX lines and records what gets written back, standing
    in for a real pyserial Serial object (readline()/write() shape only)."""

    def __init__(self, lines: list[bytes]):
        self._lines = list(lines)
        self.written: list[bytes] = []

    def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)

    def write(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)


def test_decode_rx_line_parses_valid_data_frame():
    payload = encode_data_frame(DataFrame(sender_id=1, needs_water=NeedsWater.TRUE, battery_pct=80, timestamp=42))
    line = f"RX {payload.hex()} -52\n"

    received = decode_rx_line(line)

    assert received is not None
    assert received.frame == DataFrame(sender_id=1, needs_water=NeedsWater.TRUE, battery_pct=80, timestamp=42)
    assert received.rssi == -52


def test_decode_rx_line_parses_valid_announce_frame():
    payload = encode_announce_frame(AnnounceFrame(factory_id=0xABCD))
    line = f"RX {payload.hex()} -55\n"

    received = decode_rx_line(line)

    assert received is not None
    assert received.frame == AnnounceFrame(factory_id=0xABCD)
    assert received.rssi == -55


def test_decode_rx_line_rejects_malformed_lines():
    assert decode_rx_line("garbage\n") is None
    assert decode_rx_line("RX notahexstring -52\n") is None
    assert decode_rx_line("RX 03 not-a-number\n") is None
    assert decode_rx_line("RX 03\n") is None  # missing rssi field


def test_encode_tx_line_matches_wire_format():
    assert encode_tx_line(bytes([0x01, 0x02, 0x03])) == "TX 010203\n"


def test_serial_bridge_dispatches_decoded_frames_from_fake_port():
    beacon = BeaconFrame(sender_id=0, hop_count=0)
    payload = encode_beacon_frame(beacon)
    port = FakeSerialPort([f"RX {payload.hex()} -40\n".encode("ascii")])

    received_frames = []
    bridge = SerialBridge(port, on_frame=received_frames.append)

    dispatched = bridge.poll_once()

    assert dispatched is True
    assert len(received_frames) == 1
    assert received_frames[0].frame == beacon
    assert received_frames[0].rssi == -40


def test_serial_bridge_ignores_malformed_lines_without_crashing():
    port = FakeSerialPort([b"not a valid line\n", b""])
    bridge = SerialBridge(port, on_frame=lambda _: (_ for _ in ()).throw(AssertionError("should not be called")))

    assert bridge.poll_once() is False
    assert bridge.poll_once() is False  # EOF


def test_serial_bridge_send_writes_tx_line_to_port():
    port = FakeSerialPort([])
    bridge = SerialBridge(port, on_frame=lambda _: None)

    bridge.send(bytes([0x01, 0x00, 0x00, 0x00]))

    assert port.written == [b"TX 01000000\n"]
