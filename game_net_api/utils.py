import time
import struct

HDR_FMT = "!B H B I"  # channel(1), seq(2), retrans_count(1), timestamp(4)
HDR_SIZE = struct.calcsize(HDR_FMT)


def now_ms() -> int:
    return int(time.monotonic_ns() / 1_000_000)


def calc_latency(sent_timestamp: int, arrived_timestamp: int) -> int:
    """
    Calculate latency in milliseconds.
    Assume only lower 32 bits of timestamps are considered.
    """
    # Use unsigned 32-bit modulo arithmetic to account for 32-bit wrap-around
    # e.g., when the sender's lower-32-bit timestamp wraps from 0xFFFFFFFF -> 0x00000000
    # compute the difference modulo 2**32 so the result is a non-negative latency value.
    send = sent_timestamp & 0xFFFFFFFF
    arrival = arrived_timestamp & 0xFFFFFFFF

    return (arrival - send) & 0xFFFFFFFF


def pack_packet(channel: int, seq: int, retrans_count: int = 0, payload: bytes | None = None) -> bytes:
    timestamp = now_ms()
    header = struct.pack(HDR_FMT, channel & 0xFF, seq & 0xFFFF, retrans_count & 0xFF, timestamp & 0xFFFFFFFF)
    if not payload:
        return header
    return header + payload


def unpack_packet(data: bytes):
    if len(data) < HDR_SIZE:
        raise ValueError("Data too short")
    channel, seq, retrans_count, timestamp = struct.unpack(HDR_FMT, data[:HDR_SIZE])
    return channel, seq, retrans_count, timestamp, data[HDR_SIZE:]
