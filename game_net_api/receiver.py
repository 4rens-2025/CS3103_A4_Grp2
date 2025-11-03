import asyncio
from typing import Callable, List, Tuple

from game_net_api.base import (
    CHAN_ACK,
    CHAN_RELIABLE,
    CHAN_UNRELIABLE,
    MAX_SEQ_NUM,
    WINDOW_SIZE,
    BaseGameNetAPI,
)
from game_net_api.utils import calc_latency, now_ms, pack_packet, unpack_packet

# For each received packet, we set a timeout to indicate the longest time 
# this received packet should stay in buffer before being delivered
SKIP_TIMEOUT = 0.2  # seconds, 200 ms


class GameNetReceiver(BaseGameNetAPI):
    def __init__(self, app_name: str, bind_addr: Tuple[str, int], src_addr: Tuple[str, int], deliver_cb: Callable):
        super().__init__(app_name, bind_addr)

        # Generic receiver states
        self._src_addr = src_addr
        self._deliver_cb = deliver_cb

        # Additional states for reliable channel
        self._base_seq = 0  # smallest expected seq in window
        self._received = [False] * WINDOW_SIZE
        self._buffer: List[Tuple | None] = [None] * WINDOW_SIZE
        self._skip_timers = {}  # seq -> skip timers

        # Metrics
        self.reliable_channel_metrics = {
            "received_packets": 0,
            "received_bytes": 0,
            "latency_sum_ms": 0.0,
            "latency_min_ms": float("inf"),
            "latency_max_ms": 0.0,
            "jitter_ms": 0.0,
            "skipped_packets": 0,
        }
        self.unreliable_channel_metrics = {
            "received_packets": 0,
            "received_bytes": 0,
            "latency_sum_ms": 0.0,
            "latency_min_ms": float("inf"),
            "latency_max_ms": 0.0,
            "jitter_ms": 0.0,
        }

    def stop(self):
        for timer in self._skip_timers.values():
            timer.cancel()
        self._skip_timers.clear()
        super().stop()

    def _process_datagram(self, data: bytes, addr: Tuple[str, int]):
        if addr != self._src_addr:
            print(f"[WARNING] Data received from {addr} when src_addr is {self._src_addr}")
            return
        
        arrival_timestamp = now_ms()
        try:
            channel, seq, retrans_count, sent_timestamp, payload = unpack_packet(data)
        except Exception as e:
            print(f"[ServerProtocol] bad pkt from {addr}: {e}")
            return

        if channel == CHAN_UNRELIABLE:
            self._handle_unreliable(seq, retrans_count, payload, sent_timestamp, arrival_timestamp)
        elif channel == CHAN_RELIABLE:
            self._handle_reliable(seq, retrans_count, payload, sent_timestamp, arrival_timestamp)
        elif channel == CHAN_ACK:
            print(f"[WARNING] ACK packet received from {addr} on Receiver")
            pass  # Ignore ACK packets for server

    def _handle_unreliable(
        self, seq: int, retrans_count: int, payload: bytes, sent_timestamp: int, arrival_timestamp: int
    ):
        latency = calc_latency(sent_timestamp, arrival_timestamp)
        self._deliver_cb(seq, False, retrans_count, payload, arrival_timestamp, latency)

        self._update_metrics(CHAN_UNRELIABLE, sent_timestamp, arrival_timestamp, payload)

    def _handle_reliable(
        self, seq: int, retrans_count: int, payload: bytes, sent_timestamp: int, arrival_timestamp: int
    ):
        # If seq outside window [base_seq - WINDOW_SIZE, base_seq + WINDOW_SIZE), ignore
        if not self._in_window(seq, self._base_seq) and not self._in_window(
            seq, (self._base_seq - WINDOW_SIZE) % MAX_SEQ_NUM
        ):
            return

        # If within window, immediately send ACK
        ack_pkt = pack_packet(CHAN_ACK, seq)
        self.transport.sendto(ack_pkt, self._src_addr)

        # Ignore duplicate packet
        if not self._in_window(seq, self._base_seq) or self._received[seq % WINDOW_SIZE]:
            return

        latency = calc_latency(sent_timestamp, arrival_timestamp)
        self._buffer[seq % WINDOW_SIZE] = (seq, retrans_count, payload, arrival_timestamp, latency)
        self._received[seq % WINDOW_SIZE] = True

        # If out of order, start skip timer
        if seq != self._base_seq:
            self._start_skip_timer(seq)

        self._try_deliver()
        self._update_metrics(CHAN_RELIABLE, sent_timestamp, arrival_timestamp, payload)

    def _try_deliver(self):
        while self._received[self._base_seq % WINDOW_SIZE]:
            buf = self._buffer[self._base_seq % WINDOW_SIZE]
            if buf is not None:
                seq, retrans_count, payload, arrival_timestamp, latency = buf
                self._deliver_cb(seq, True, retrans_count, payload, arrival_timestamp, latency)
            else:
                self.reliable_channel_metrics["skipped_packets"] += 1

            if self._base_seq in self._skip_timers:
                self._skip_timers[self._base_seq].cancel()
                del self._skip_timers[self._base_seq]

            self._buffer[self._base_seq % WINDOW_SIZE] = None
            self._received[self._base_seq % WINDOW_SIZE] = False
            self._base_seq = (self._base_seq + 1) % MAX_SEQ_NUM

    def _start_skip_timer(self, seq: int):
        async def skip_packets():
            current = asyncio.current_task()
            await asyncio.sleep(SKIP_TIMEOUT)

            # Ensure the timer is still valid
            if self._skip_timers.get(seq) != current:
                return

            # Skip lost packets before seq on timeout
            for offset in range(WINDOW_SIZE):
                check_seq = (self._base_seq + offset) % MAX_SEQ_NUM
                if check_seq == seq:
                    break

                if self._received[check_seq % WINDOW_SIZE]:
                    continue

                ack_pkt = pack_packet(CHAN_ACK, check_seq)
                self.transport.sendto(ack_pkt, self._src_addr)
                self._received[check_seq % WINDOW_SIZE] = True  # Mark as received to skip

            self._try_deliver()

        self._skip_timers[seq] = asyncio.create_task(skip_packets())

    def _update_metrics(self, channel: int, sent_timestamp: int, arrival_timestamp: int, payload: bytes):
        metrics = self.reliable_channel_metrics if channel == CHAN_RELIABLE else self.unreliable_channel_metrics

        transit_ms = calc_latency(sent_timestamp, arrival_timestamp)

        if "prev_transit_ms" not in metrics:
            metrics["prev_transit_ms"] = transit_ms

        # RFC 3550 jitter calculation (https://datatracker.ietf.org/doc/html/rfc3550#appendix-A.8)
        D = transit_ms - metrics["prev_transit_ms"]
        metrics["prev_transit_ms"] = transit_ms
        metrics["jitter_ms"] += (abs(D) - metrics["jitter_ms"]) / 16.0

        # Update latency stats
        metrics["latency_sum_ms"] += transit_ms
        metrics["latency_min_ms"] = min(metrics["latency_min_ms"], transit_ms)
        metrics["latency_max_ms"] = max(metrics["latency_max_ms"], transit_ms)

        # Packet and byte counters
        metrics["received_packets"] += 1
        metrics["received_bytes"] += len(payload)
