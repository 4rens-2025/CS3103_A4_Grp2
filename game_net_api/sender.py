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

RETRANSMISSION_TIMEOUT = 0.08  # seconds, 80 ms
MAX_RETRANSMISSION_COUNT = 10 

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
        self._buffer: List[Tuple[bytes, int] | None] = [None] * WINDOW_SIZE # (payload, retrans_count)
        self._retransmission_timers = {}  # seq -> timers for retransmission

        # Metrics
        self.reliable_channel_metrics = { "sent_packets": 0 }
        self.unreliable_channel_metrics = { "sent_packets": 0 }

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

    async def _wait_for_retransmissions_complete(self, timeout: float = 2.0):
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
            channel, seq, _, _, _ = unpack_packet(data)
        except Exception as e:
            print(f"[ServerProtocol] bad pkt from {addr}: {e}")
            return

        if channel != CHAN_ACK:
            print(f"[WARNING] Non-ACK packet received from {addr} on Sender")
            return  # Ignore non-ACK packets

        if not self._in_window(seq, self._base_seq):
            return  # Ignore ACKs outside the window

        idx = seq % WINDOW_SIZE
        if self._acked[idx]:
            return  # Ignore duplicate ACKs

        self._acked[idx] = True
        self._buffer[idx] = None
        self._cancel_timer(seq)

        self._try_advance_base()

    async def _send_unreliable(self, payload: bytes):
        # Send packet
        pkt = pack_packet(CHAN_UNRELIABLE, self._next_unreliable_seq, 0, payload)
        self.transport.sendto(pkt, self._dest_addr)

        # Update state
        self._next_unreliable_seq  = (self._next_unreliable_seq + 1) % MAX_SEQ_NUM
        self.unreliable_channel_metrics["sent_packets"] += 1

    async def _send_reliable(self, payload: bytes):
        # Ensure can still send
        await self._sem.acquire()

        # Send packet
        seq = self._next_reliable_seq
        pkt = pack_packet(CHAN_RELIABLE, seq, 0, payload)
        self.transport.sendto(pkt, self._dest_addr)

        # Update state
        self._next_reliable_seq = (self._next_reliable_seq + 1) % MAX_SEQ_NUM
        self.reliable_channel_metrics["sent_packets"] += 1

        # Update additional states
        if self._acked[seq % WINDOW_SIZE]:
            raise Exception("ACK state should not be True")
        self._buffer[seq % WINDOW_SIZE] = (payload, 0) # First buffered data has retrans_count = 0
        self._start_timer(seq)

    def _start_timer(self, seq):
        async def retransmit_on_timeout():
            current = asyncio.current_task()
            await asyncio.sleep(RETRANSMISSION_TIMEOUT)

            # Ensure the timer is still valid
            if self._retransmission_timers.get(seq) != current or self._acked[seq % WINDOW_SIZE]:
                return

            # Retransmit packet
            payload, prev_restrans_count = self._buffer[seq % WINDOW_SIZE]
            if (prev_restrans_count == MAX_RETRANSMISSION_COUNT):
                # If packet not reached max retrans count, we assume do not care about this packet anymore
                self._acked[seq % WINDOW_SIZE] = True
                self._buffer[seq % WINDOW_SIZE] = None
                self._try_advance_base()
                return
                
            
            pkt = pack_packet(CHAN_RELIABLE, seq, prev_restrans_count + 1, payload)
            self.transport.sendto(pkt, self._dest_addr)

            # Update buffer 
            self._buffer[seq % WINDOW_SIZE] = (payload, prev_restrans_count + 1)

            # Restart timer
            self._start_timer(seq)

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
