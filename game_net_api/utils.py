import time
import struct
from typing import Tuple

HDR_FMT = "!B H I"  # channel(1), seq(2), timestamp(4)
HDR_SIZE = struct.calcsize(HDR_FMT)


def now_ms() -> int:
    return int(time.monotonic_ns() / 1_000_000)

def calc_latency(sent_timestamp: int, delivered_timestamp: int) -> int:
    """
    Calculate latency in milliseconds.
    Assume only lower 32 bits of timestamps are considered.
    """
    # Use unsigned 32-bit modulo arithmetic to account for 32-bit wrap-around
    # e.g., when the sender's lower-32-bit timestamp wraps from 0xFFFFFFFF -> 0x00000000
    # compute the difference modulo 2**32 so the result is a non-negative latency value.
    sent = sent_timestamp & 0xFFFFFFFF
    delivered = delivered_timestamp & 0xFFFFFFFF
    return (delivered - sent) & 0xFFFFFFFF


def pack_packet(channel: int, seq: int, payload: bytes | None = None) -> bytes:
    timestamp = now_ms()
    header = struct.pack(HDR_FMT, channel & 0xFF, seq & 0xFFFF, timestamp & 0xFFFFFFFF)
    if not payload:
        return header
    return header + payload


def unpack_packet(data: bytes) -> Tuple[int, int, int, bytes]:
    if len(data) < HDR_SIZE:
        raise ValueError("Data too short")
    channel, seq, timestamp = struct.unpack(HDR_FMT, data[:HDR_SIZE])
    return channel, seq, timestamp, data[HDR_SIZE:]
