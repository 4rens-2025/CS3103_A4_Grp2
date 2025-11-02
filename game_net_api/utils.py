import time
import struct

HDR_FMT = "!B H I B"  # channel(1), seq(2), timestamp(4), retrans_count(1)
HDR_SIZE = struct.calcsize(HDR_FMT)


def now_ms() -> int:
    """Get timestamp in milliseconds."""
    return int(time.monotonic_ns() / 1_000_000)


def calc_latency(send_ts: int, arrival_ts: int) -> int:
    """
    Calculate latency in milliseconds.
    Assume only lower 32 bits of timestamps are considered.
    """
    # Use unsigned 32-bit modulo arithmetic to account for 32-bit wrap-around
    # e.g., when the sender's lower-32-bit timestamp wraps from 0xFFFFFFFF -> 0x00000000
    # compute the difference modulo 2**32 so the result is a non-negative latency value.
    send = send_ts & 0xFFFFFFFF
    arrival = arrival_ts & 0xFFFFFFFF

    return (arrival - send) & 0xFFFFFFFF


def pack_packet(channel: int, seq: int, payload: bytes | None = None, retrans_count: int = 0) -> bytes:
    """Pack a packet with header and optional payload.

    Args:
        channel: channel
        seq: sequence number (2 bytes)
        payload: optional payload bytes
        retrans_count: retransmission count (1 byte)
    """

    ts = now_ms()
    header = struct.pack(HDR_FMT, channel & 0xFF, seq & 0xFFFF, ts & 0xFFFFFFFF, retrans_count & 0xFF)
    if payload:
        return header + payload
    return header


def unpack_packet(data: bytes):
    """Unpack a packet into (channel, seq, timestamp, retrans_count, payload)."""

    if len(data) < HDR_SIZE:
        raise ValueError("too-short")
    ch, seq, ts, rtx = struct.unpack(HDR_FMT, data[:HDR_SIZE])
    return ch, seq, ts, rtx, data[HDR_SIZE:]
