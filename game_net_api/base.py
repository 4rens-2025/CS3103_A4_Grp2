from abc import abstractmethod
import asyncio
from typing import Callable, Tuple

CHAN_RELIABLE = 0
CHAN_UNRELIABLE = 1
CHAN_ACK = 2

WINDOW_SIZE = 32  # packets
MAX_SEQ_NUM = WINDOW_SIZE * 2


class CustomProtocol(asyncio.DatagramProtocol):
    def __init__(self, app_name: str, on_receive: Callable[[bytes, Tuple[str, int]], None]):
        self.app_name = app_name
        self.on_receive = on_receive

    def connection_made(self, transport):
        print(f"[GameNetAPI({self.app_name})] listening on {transport.get_extra_info('sockname')}")

    def datagram_received(self, data, addr):
        self.on_receive(data, addr)

    def error_received(self, exc):
        print(f"[{self.app_name}] error:", exc)


class BaseGameNetAPI:
    def __init__(self, app_name: str, bind_addr: Tuple[str, int]):
        self.app_name = app_name
        self.bind_addr = bind_addr
        self.reliable_channel_metric = {"sent_packets": 0, "received_packets": 0}
        self.unreliable_channel_metric = {"sent_packets": 0, "received_packets": 0}

        self._transport = None

    @property
    def transport(self):
        if self._transport is None:
            raise RuntimeError("not started")

        return self._transport

    async def start(self):
        if self._transport is not None:
            return
        loop = asyncio.get_running_loop()
        protocol = CustomProtocol(app_name=self.app_name, on_receive=self._process_datagram)
        transport, _ = await loop.create_datagram_endpoint(lambda: protocol, local_addr=self.bind_addr)
        self._transport = transport

    async def stop(self):
        self.transport.close()
        self._transport = None

        return self.reliable_channel_metric, self.unreliable_channel_metric

    @abstractmethod
    def _process_datagram(self, data: bytes, addr: Tuple[str, int]):
        pass

    def _in_window(self, seq: int, base_seq: int) -> bool:
        return (seq - base_seq) % MAX_SEQ_NUM < WINDOW_SIZE
