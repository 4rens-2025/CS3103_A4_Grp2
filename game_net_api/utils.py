import time
import struct

HDR_FMT = "!B H I"  # channel(1), seq(2), timestamp(4)
HDR_SIZE = struct.calcsize(HDR_FMT)


def now_ms() -> int:
    return int(time.time() * 1000) & 0xFFFFFFFF


def pack_packet(channel: int, seq: int, payload: bytes) -> bytes:
    ts = now_ms()
    return struct.pack(HDR_FMT, channel & 0xFF, seq & 0xFFFF, ts) + payload


def unpack_packet(data: bytes):
    if len(data) < HDR_SIZE:
        raise ValueError("too-short")
    ch, seq, ts = struct.unpack(HDR_FMT, data[:HDR_SIZE])
    return ch, seq, ts, data[HDR_SIZE:]
