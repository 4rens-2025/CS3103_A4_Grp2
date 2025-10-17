import struct
from typing import Callable, List, Tuple, override

from game_net_api.base import (
    CHAN_ACK,
    CHAN_RELIABLE,
    CHAN_UNRELIABLE,
    MAX_SEQ_NUM,
    WINDOW_SIZE,
    BaseGameNetAPI,
)
from game_net_api.utils import HDR_FMT, now_ms, unpack_packet

SKIP_TIMEOUT = 200  # ms


class GameNetReceiver(BaseGameNetAPI):
    def __init__(self, app_name: str, bind_addr: Tuple[str, int], deliver_cb: Callable):
        super().__init__(app_name, bind_addr)
        self._deliver_cb = deliver_cb
        self._expected_seq = None

        # Circular buffer of length WINDOW_SIZE
        self.buffer: List[Tuple | None] = [None] * WINDOW_SIZE
        self.seqnum = [-1] * WINDOW_SIZE
        self.received = [False] * WINDOW_SIZE
        self.base_seq = 0  # smallest expected seq in window

    @override
    def _process_datagram(self, data: bytes, addr: Tuple[str, int]):
        try:
            ch, seq, ts, payload = unpack_packet(data)
        except Exception as e:
            print(f"[ServerProtocol] bad pkt from {addr}: {e}")
            return

        if ch == CHAN_UNRELIABLE:
            self._handle_unreliable(addr, seq, payload)
        elif ch == CHAN_RELIABLE:
            self._handle_reliable(addr, seq, payload)
        elif ch == CHAN_ACK:
            pass  # Ignore ACK packets for server

    def _handle_unreliable(self, addr: Tuple[str, int], seq: int, payload: bytes):
        self.unreliable_channel_metric["received_packets"] += 1

        # Do nothing and call the deliver callback
        self._deliver_cb(addr, seq, CHAN_UNRELIABLE, payload)

    def _handle_reliable(self, addr: Tuple[str, int], seq: int, payload: bytes):
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
        if not self.received[idx]:
            self.buffer[idx] = (addr, seq, payload)
            self.seqnum[idx] = seq
            self.received[idx] = True

        self._try_deliver()

    def _make_ack(self, seq: int) -> bytes:
        ts = now_ms()
        return struct.pack(HDR_FMT, CHAN_ACK, seq & 0xFFFF, ts)

    def _try_deliver(self):
        while self.received[self.base_seq % WINDOW_SIZE]:
            self.reliable_channel_metric["received_packets"] += 1
            idx = self.base_seq % WINDOW_SIZE
            buf = self.buffer[idx]

            if buf is None:
                print("Unexpected None in buffer")
            else:
                addr, seq, payload = buf
                self._deliver_cb(addr, seq, CHAN_RELIABLE, payload)

            self.buffer[idx] = None
            self.received[idx] = False
            self.seqnum[idx] = -1
            self.base_seq = (self.base_seq + 1) % MAX_SEQ_NUM
