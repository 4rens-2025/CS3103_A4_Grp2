import asyncio
from typing import List, Tuple, override

from game_net_api.base import (
    CHAN_ACK,
    CHAN_RELIABLE,
    CHAN_UNRELIABLE,
    MAX_SEQ_NUM,
    WINDOW_SIZE,
    BaseGameNetAPI,
)
from game_net_api.utils import pack_packet, unpack_packet

RETRANSMISSION_TIMEOUT = 0.08  # seconds, 80 ms


class GameNetSender(BaseGameNetAPI):
    def __init__(self, app_name: str, bind_addr: Tuple[str, int]):
        super().__init__(app_name=app_name, bind_addr=bind_addr)
        self._next_seq = [0, 0]  # [reliable, unreliable]

        # Reliable channel state
        self._base_seq = 0  # smallest unacked seq in window
        self._sem = asyncio.Semaphore(WINDOW_SIZE)  # limit sender window size
        # Buffer of packets for retransmission
        self._buffer: List[Tuple[bytes, Tuple[str, int]] | None] = [None] * WINDOW_SIZE
        self._acked = [False] * WINDOW_SIZE  # acked flags for packets in window
        self._timers = {}  # seq -> timers for retransmission

        # Initialize metrics
        self.reliable_channel_metric["sent_packets"] = 0
        self.unreliable_channel_metric["sent_packets"] = 0

    async def send(self, payload: str, reliable: bool, dest: Tuple[str, int]) -> int:
        """
        Send a packet with the given payload to the destination address.

        Args:
            payload (str): The payload to send.
            reliable (bool): Whether to send through the reliable channel.
            dest (Tuple[str, int]): The destination address.
        """
        if reliable:
            return await self._send_reliable(payload, dest)
        else:
            return await self._send_unreliable(payload, dest)

    @override
    def stop(self):
        # Clean up all timers on stop
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()

        return super().stop()

    @override
    def _process_datagram(self, data: bytes, addr: Tuple[str, int]):
        try:
            ch, seq, _, _ = unpack_packet(data)
        except Exception as e:
            print(f"[ServerProtocol] bad pkt from {addr}: {e}")
            return

        if ch != CHAN_ACK:
            return  # Ignore non-ACK packets

        if not self._in_window(seq, self._base_seq):
            return  # Ignore ACKs outside the window

        idx = seq % WINDOW_SIZE
        if self._acked[idx]:
            return  # Ignore duplicate ACKs

        self._cancel_timer(seq)
        self._acked[idx] = True
        self._try_advance_base()

    async def _send_unreliable(self, payload: str, dest: Tuple[str, int]) -> int:
        """Send an unreliable packet."""
        next_seq = self._next_seq[CHAN_UNRELIABLE]

        pkt = pack_packet(CHAN_UNRELIABLE, next_seq, payload.encode("utf-8"))

        self.unreliable_channel_metric["sent_packets"] += 1
        self.transport.sendto(pkt, dest)

        self._next_seq[CHAN_UNRELIABLE] += 1
        self._next_seq[CHAN_UNRELIABLE] %= MAX_SEQ_NUM

        return next_seq

    async def _send_reliable(self, payload: str, dest: Tuple[str, int]) -> int:
        """Send a reliable packet."""
        await self._sem.acquire()

        next_seq = self._next_seq[CHAN_RELIABLE]
        self._next_seq[CHAN_RELIABLE] += 1
        self._next_seq[CHAN_RELIABLE] %= MAX_SEQ_NUM

        pkt = pack_packet(CHAN_RELIABLE, next_seq, payload.encode("utf-8"))

        self.reliable_channel_metric["sent_packets"] += 1
        self.transport.sendto(pkt, dest)

        idx = next_seq % WINDOW_SIZE
        self._buffer[idx] = (pkt, dest)
        self._acked[idx] = False
        self._start_timer(next_seq)

        return next_seq

    def _start_timer(self, seq):
        """Start retransmission timer for the given seq."""

        async def retransmit_on_timeout():
            current = asyncio.current_task()
            await asyncio.sleep(RETRANSMISSION_TIMEOUT)

            # Ensure the timer is still valid
            if self._timers.get(seq) != current:
                return

            # Retransmit if not acked then restart timer
            if not self._acked[seq % WINDOW_SIZE]:
                buf = self._buffer[seq % WINDOW_SIZE]
                if buf:
                    pkt, dest = buf
                    self.transport.sendto(pkt, dest)

                self._start_timer(seq)

        self._timers[seq] = asyncio.create_task(retransmit_on_timeout())

    def _cancel_timer(self, seq):
        """Cancel retransmission timer for the given seq."""
        if seq in self._timers:
            self._timers[seq].cancel()
            del self._timers[seq]

    def _try_advance_base(self):
        """Advance the base seq if possible."""
        while self._acked[self._base_seq % WINDOW_SIZE]:
            idx = self._base_seq % WINDOW_SIZE
            self._buffer[idx] = None
            self._acked[idx] = False
            self._base_seq = (self._base_seq + 1) % MAX_SEQ_NUM

            # Release semaphore slot for new packet
            self._sem.release()
