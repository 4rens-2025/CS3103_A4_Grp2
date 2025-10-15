import asyncio
from typing import Tuple

from game_net_api.utils import pack_packet

CHAN_RELIABLE = 0
CHAN_UNRELIABLE = 1
CHAN_ACK = 2

MAX_SEQ = 0xFFFF


class BaseGameNetAPI:
    def __init__(self, protocol: asyncio.DatagramProtocol, bind_addr: Tuple[str, int]):
        self.protocol = protocol
        self.bind_addr = bind_addr
        self.transport = None
        self._seq = 0

    async def start(self):
        if self.transport is not None:
            return
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: self.protocol, local_addr=self.bind_addr
        )
        self.transport = transport

    async def stop(self):
        if not self.transport:
            return

        self.transport.close()
        self.transport = None
        await asyncio.sleep(0)

    async def send(self, payload: str, reliable: bool, dest: Tuple[str, int]) -> int:
        if self.transport is None:
            raise RuntimeError("not started")

        payload_b = payload.encode("utf-8")

        self._seq = (self._seq + 1) & MAX_SEQ
        if self._seq == 0:
            self._seq = 1
        ch = CHAN_RELIABLE if reliable else CHAN_UNRELIABLE
        pkt = pack_packet(ch, self._seq, payload_b)

        self.transport.sendto(pkt, dest)

        return self._seq
