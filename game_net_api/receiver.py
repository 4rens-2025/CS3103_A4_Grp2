import asyncio
from typing import Callable, List, Tuple, override

from game_net_api.base import (
    CHAN_ACK,
    CHAN_RELIABLE,
    CHAN_UNRELIABLE,
    MAX_SEQ_NUM,
    WINDOW_SIZE,
    BaseGameNetAPI,
)
from game_net_api.utils import calc_latency, now_ms, pack_packet, unpack_packet

SKIP_TIMEOUT = 0.2  # seconds, 200 ms


class GameNetReceiver(BaseGameNetAPI):
    def __init__(self, app_name: str, bind_addr: Tuple[str, int], deliver_cb: Callable):
        super().__init__(app_name, bind_addr)
        self._deliver_cb = deliver_cb

        # Circular buffer of length WINDOW_SIZE
        self.buffer: List[Tuple | None] = [None] * WINDOW_SIZE
        self.received = [False] * WINDOW_SIZE
        self.base_seq = 0  # smallest expected seq in window
        self.skip_timers = {}  # seq -> skip timers

        self.reliable_channel_metric = {
            "received_packets": 0,
            "received_bytes": 0,
            "latency_sum_ms": 0.0,
            "latency_min_ms": float("inf"),
            "latency_max_ms": 0.0,
            "jitter_ms": 0.0,
            "skipped_packets": 0,
        }
        self.unreliable_channel_metric = {
            "received_packets": 0,
            "received_bytes": 0,
            "latency_sum_ms": 0.0,
            "latency_min_ms": float("inf"),
            "latency_max_ms": 0.0,
            "jitter_ms": 0.0,
        }

    @override
    def stop(self):
        for timer in self.skip_timers.values():
            timer.cancel()
        self.skip_timers.clear()
        return super().stop()

    @override
    def _process_datagram(self, data: bytes, addr: Tuple[str, int]):
        arrival_ts = now_ms()
        try:
            ch, seq, send_ts, payload = unpack_packet(data)
        except Exception as e:
            print(f"[ServerProtocol] bad pkt from {addr}: {e}")
            return

        if ch == CHAN_UNRELIABLE:
            self._handle_unreliable(addr, seq, send_ts, arrival_ts, payload)
        elif ch == CHAN_RELIABLE:
            self._handle_reliable(addr, seq, send_ts, arrival_ts, payload)
        elif ch == CHAN_ACK:
            pass  # Ignore ACK packets for server

    def _handle_unreliable(
        self, addr: Tuple[str, int], seq: int, send_ts: int, arrival_ts: int, payload: bytes
    ):
        # Do nothing and call the deliver callback
        latency = arrival_ts & 0xFFFFFFFF - send_ts
        self._deliver_cb(seq, CHAN_UNRELIABLE, payload, arrival_ts, latency)

        self._update_metrics(CHAN_UNRELIABLE, send_ts, arrival_ts, payload)

    def _handle_reliable(
        self, addr: Tuple[str, int], seq: int, send_ts: int, arrival_ts: int, payload: bytes
    ):
        # If seq outside window [base_seq - WINDOW_SIZE, base_seq + WINDOW_SIZE), ignore
        if not self._in_window(seq, self.base_seq) and not self._in_window(
            seq, (self.base_seq - WINDOW_SIZE) % MAX_SEQ_NUM
        ):
            return

        # If within window, immediately send ACK
        ack_pkt = self._make_ack(seq)
        self.transport.sendto(ack_pkt, addr)

        # If seq is before base_seq, it is a duplicate packet; ignore
        if not self._in_window(seq, self.base_seq):
            return

        idx = seq % WINDOW_SIZE

        if self.received[idx]:
            return  # Duplicate packet; ignore

        latency = calc_latency(send_ts, arrival_ts)
        self.buffer[idx] = (addr, seq, payload, arrival_ts, latency)
        self.received[idx] = True

        # If out of order, start skip timer
        if seq != self.base_seq:
            self._start_skip_timer(seq, addr)
        else:
            self._try_deliver()

        self._update_metrics(CHAN_RELIABLE, send_ts, arrival_ts, payload)

    def _try_deliver(self):
        """Try to deliver in-order packets from the buffer."""
        while self.received[self.base_seq % WINDOW_SIZE]:
            idx = self.base_seq % WINDOW_SIZE
            buf = self.buffer[idx]

            if buf is not None:
                _, seq, payload, arrival_ts, latency = buf
                self._deliver_cb(seq, CHAN_RELIABLE, payload, arrival_ts, latency)
            else:
                self.reliable_channel_metric["skipped_packets"] += 1

            if self.base_seq in self.skip_timers:
                self.skip_timers[self.base_seq].cancel()
                del self.skip_timers[self.base_seq]

            self.buffer[idx] = None
            self.received[idx] = False
            self.base_seq = (self.base_seq + 1) % MAX_SEQ_NUM

    def _start_skip_timer(self, seq: int, addr: Tuple[str, int]):
        """Start a skip timer for the given seq number."""

        async def skip_packet():
            """Skip packets before seq after timeout."""
            current = asyncio.current_task()
            await asyncio.sleep(SKIP_TIMEOUT)

            # Ensure the timer is still valid
            if self.skip_timers.get(seq) != current:
                return

            # Skip lost packets before seq on timeout
            for offset in range(WINDOW_SIZE):
                check_seq = (self.base_seq + offset) % MAX_SEQ_NUM
                if check_seq == seq:
                    break

                idx = check_seq % WINDOW_SIZE

                if self.received[idx]:
                    continue

                ack_pkt = self._make_ack(check_seq)
                self.transport.sendto(ack_pkt, addr)
                self.received[idx] = True  # Mark as received to skip

            self._try_deliver()

        self.skip_timers[seq] = asyncio.create_task(skip_packet())

    def _make_ack(self, seq: int) -> bytes:
        """Create an ACK packet for the given seq number."""
        return pack_packet(CHAN_ACK, seq)

    def _update_metrics(self, ch: int, send_ts: int, arrival_ms: int, payload: bytes):
        metric = self.reliable_channel_metric if ch == CHAN_RELIABLE else self.unreliable_channel_metric

        # Calculate one-way latency
        transit_ms = calc_latency(send_ts, arrival_ms)

        if "prev_transit_ms" not in metric:
            metric["prev_transit_ms"] = transit_ms

        # RFC 3550 jitter calculation (https://datatracker.ietf.org/doc/html/rfc3550#appendix-A.8)
        D = transit_ms - metric["prev_transit_ms"]
        metric["prev_transit_ms"] = transit_ms
        metric["jitter_ms"] += (abs(D) - metric["jitter_ms"]) / 16.0

        # Update latency stats
        metric["latency_sum_ms"] += transit_ms
        metric["latency_min_ms"] = min(metric["latency_min_ms"], transit_ms)
        metric["latency_max_ms"] = max(metric["latency_max_ms"], transit_ms)

        # Packet and byte counters
        metric["received_packets"] += 1
        metric["received_bytes"] += len(payload)
