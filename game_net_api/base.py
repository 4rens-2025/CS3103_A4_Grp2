from abc import abstractmethod
import asyncio
from typing import Callable, Tuple

CHAN_UNRELIABLE = 0
CHAN_RELIABLE = 1
CHAN_ACK = 2

MAX_SEQ_NUM = 2**16  # 16-bit sequence number
WINDOW_SIZE = 128  # packets


class CustomProtocol(asyncio.DatagramProtocol):
    def __init__(self, app_name: str, on_receive: Callable[[bytes, Tuple[str, int]], None]):
        self._app_name = app_name
        self._on_receive = on_receive

    def connection_made(self, transport):
        print(f"[GameNetAPI({self._app_name})] listening on {transport.get_extra_info('sockname')}")

    def datagram_received(self, data, addr):
        self._on_receive(data, addr)

    def error_received(self, exc):
        print(f"[{self._app_name}] error:", exc)

class BaseGameNetAPI:
    def __init__(self, app_name: str):
        self._app_name = app_name
        self._transport = None

        self.reliable_channel_metrics = {}
        self.unreliable_channel_metrics = {}

    @property
    def transport(self):
        if self._transport is None:
            raise RuntimeError("Not started")

        return self._transport
    
    async def _start(self, bind_addr: Tuple[str, int]):
        if self._transport is not None:
            raise RuntimeError("Already started")
        
        loop = asyncio.get_running_loop()
        protocol = CustomProtocol(app_name=self._app_name, on_receive=self._process_datagram)
        transport, _ = await loop.create_datagram_endpoint(lambda: protocol, local_addr=bind_addr)
        self._transport = transport

    def _stop(self):
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    @abstractmethod
    def _process_datagram(self, data: bytes, addr: Tuple[str, int]):
        pass

    def _in_window(self, seq: int, base_seq: int) -> bool:
        return (seq - base_seq) % MAX_SEQ_NUM < WINDOW_SIZE
