import time
import struct

HDR_FMT = "!B H I"  # channel(1), seq(2), timestamp(4)
HDR_SIZE = struct.calcsize(HDR_FMT)


def now_ms() -> int:
    """Get timestamp in milliseconds."""
    return int(time.time() * 1000)


def calc_latency(send_ts: int, arrival_ts: int) -> int:
    """
    Calculate latency in milliseconds.
    Assume only lower 32 bits of timestamps are considered.
    """
    return (arrival_ts & 0xFFFFFFFF) - (send_ts & 0xFFFFFFFF)


def pack_packet(channel: int, seq: int, payload: bytes | None = None) -> bytes:
    """Pack a packet with header and optional payload."""

    ts = now_ms()
    header = struct.pack(HDR_FMT, channel & 0xFF, seq & 0xFFFF, ts & 0xFFFFFFFF)
    if payload:
        return header + payload
    return header


def unpack_packet(data: bytes):
    """Unpack a packet into (channel, seq, timestamp, payload)."""

    if len(data) < HDR_SIZE:
        raise ValueError("too-short")
    ch, seq, ts = struct.unpack(HDR_FMT, data[:HDR_SIZE])
    return ch, seq, ts, data[HDR_SIZE:]
