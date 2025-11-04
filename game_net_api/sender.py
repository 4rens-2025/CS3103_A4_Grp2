import asyncio
from typing import List, Tuple

from game_net_api.base import (
    CHAN_ACK,
    CHAN_RELIABLE,
    CHAN_UNRELIABLE,
    MAX_SEQ_NUM,
    WINDOW_SIZE,
    BaseGameNetAPI,
)
from game_net_api.utils import pack_packet, unpack_packet

RETRANSMISSION_TIMEOUT = 0.1  # seconds, 100 ms
MAX_RETRANSMISSION_COUNT = 3

class GameNetSender(BaseGameNetAPI):
    def __init__(self, app_name: str):
        super().__init__(app_name=app_name)

        # Generic sender states
        self._dest_addr = None
        self._next_reliable_seq = 0
        self._next_unreliable_seq = 0

        # Additional states for reliable channel
        self._sem = asyncio.Semaphore(WINDOW_SIZE)  # limit sender window size
        self._base_seq = 0  # smallest unacked seq in window
        self._acked = [False] * WINDOW_SIZE  # acked flags for packets in window
        self._buffer: List[bytes | None] = [None] * WINDOW_SIZE
        self._retransmission_timers = {}  # seq -> timers for retransmission

        # Metrics
        self.reliable_channel_metrics = { "sent_packets": 0, "retransmissions": 0}
        self.unreliable_channel_metrics = { "sent_packets": 0, "restransmissions": 0 }

    async def connect(self, dest_addr: Tuple[str, int], bind_addr: Tuple[str, int] = None):
        addr = bind_addr if bind_addr is not None else ('0.0.0.0', 0)
        await self._start(addr)
        self._dest_addr = dest_addr

    async def send(self, payload: bytes, is_reliable: bool):
        if is_reliable:
            await self._send_reliable(payload)
        else:
            await self._send_unreliable(payload)

    async def close(self, timeout: float = 2.0):
        await self._wait_for_retransmissions_complete(timeout)
        self._stop()

    async def _wait_for_retransmissions_complete(self, timeout: float):
        async def wait_for_buffers_empty():
            while not all(buf is None for buf in self._buffer):
                await asyncio.sleep(0.01)  # small delay to yield control
        try:
            await asyncio.wait_for(wait_for_buffers_empty(), timeout)
        except asyncio.TimeoutError:
            print("[WARNING] Timeout waiting for ACKs, stopping anyway.")
    
        for timer in self._retransmission_timers.values():
            timer.cancel()
        self._retransmission_timers.clear()
    
    # Process ACKs
    def _process_datagram(self, data: bytes, addr: Tuple[str, int]):
        if addr != self._dest_addr:
            print(f"[WARNING] Data received from {addr} when dest_addr is {self._dest_addr}")
            return
        
        try:
            channel, seq, _, _ = unpack_packet(data)
        except Exception as e:
            print(f"[ServerProtocol] bad pkt from {addr}: {e}")
            return

        if channel != CHAN_ACK:
            print(f"[WARNING] Non-ACK packet received from {addr} on Sender")
            return  # Ignore non-ACK packets

        if not self._in_window(seq, self._base_seq):
            return  # Ignore ACKs outside the window

        if self._acked[seq % WINDOW_SIZE]:
            return  # Ignore duplicate ACKs

        self._acked[seq % WINDOW_SIZE] = True
        self._buffer[seq % WINDOW_SIZE] = None
        self._cancel_timer(seq)

        self._try_advance_base()

    async def _send_unreliable(self, payload: bytes):
        # Send data
        packet = pack_packet(CHAN_UNRELIABLE, self._next_unreliable_seq, payload)
        self.transport.sendto(packet, self._dest_addr)

        # Update state
        self._next_unreliable_seq  = (self._next_unreliable_seq + 1) % MAX_SEQ_NUM
        self.unreliable_channel_metrics["sent_packets"] += 1

    async def _send_reliable(self, payload: bytes):
        # Ensure can still send
        await self._sem.acquire()

        # Send packet
        seq = self._next_reliable_seq
        packet = pack_packet(CHAN_RELIABLE, seq, payload)
        self.transport.sendto(packet, self._dest_addr)

        # Update state
        self._next_reliable_seq = (self._next_reliable_seq + 1) % MAX_SEQ_NUM
        self.reliable_channel_metrics["sent_packets"] += 1

        # Update additional states
        assert not self._acked[seq % WINDOW_SIZE], "ACK state invalid before send"
        self._buffer[seq % WINDOW_SIZE] = packet
        self._start_timer(seq)

    def _start_timer(self, seq, retransmissions = 0):
        async def retransmit_on_timeout():
            current = asyncio.current_task()
            await asyncio.sleep(RETRANSMISSION_TIMEOUT)

            # Ensure the timer is still valid
            if self._retransmission_timers.get(seq) != current:
                return
            if self._acked[seq % WINDOW_SIZE] or self._buffer[seq % WINDOW_SIZE] is None:
                return

            # If retransmitted more than max count
            if (retransmissions > MAX_RETRANSMISSION_COUNT):
                # If packet not reached max retrans count, we assume do not care about this packet anymore
                self._acked[seq % WINDOW_SIZE] = True
                self._buffer[seq % WINDOW_SIZE] = None
                self._try_advance_base()
                return
                
            self.transport.sendto(self._buffer[seq % WINDOW_SIZE], self._dest_addr)
            self.reliable_channel_metrics["retransmissions"] += 1

            # Restart timer
            self._start_timer(seq, retransmissions + 1)

        self._retransmission_timers[seq] = asyncio.create_task(retransmit_on_timeout())

    def _cancel_timer(self, seq):
        if seq in self._retransmission_timers:
            self._retransmission_timers[seq].cancel()
            del self._retransmission_timers[seq]

    def _try_advance_base(self):
        while self._acked[self._base_seq % WINDOW_SIZE]:
            self._acked[self._base_seq % WINDOW_SIZE] = False
            self._base_seq = (self._base_seq + 1) % MAX_SEQ_NUM
            self._sem.release()
