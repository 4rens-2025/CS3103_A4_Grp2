import asyncio
from typing import Callable, Tuple, override

from game_net_api.base import BaseGameNetAPI
from game_net_api.utils import unpack_packet


class ServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, deliver_cb: Callable | None):
        self.deliver_cb = deliver_cb
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        print(f"Server started on {transport.get_extra_info('sockname')}")

    def datagram_received(self, data, addr):
        try:
            ch, seq, ts, payload = unpack_packet(data)
        except Exception as e:
            print(f"[ServerProtocol] bad pkt from {addr}: {e}")
            return

        if self.deliver_cb:
            maybe = self.deliver_cb(addr, seq, ch, payload)
            if asyncio.iscoroutine(maybe):
                asyncio.create_task(maybe)

    def error_received(self, exc):
        print("[ServerProtocol] error:", exc)


class GameServer(BaseGameNetAPI):
    def __init__(self, bind_addr: Tuple[str, int], deliver_cb: Callable | None = None):
        def callback(addr, seq, ch, payload):
            self._increment_received_packets()
            if deliver_cb:
                return deliver_cb(addr, seq, ch, payload)

        super().__init__(protocol=ServerProtocol(deliver_cb=callback), bind_addr=bind_addr)
        self.received_packets = 0

    def _increment_received_packets(self):
        self.received_packets += 1

    @override
    async def stop(self):
        await super().stop()
        return self.received_packets
