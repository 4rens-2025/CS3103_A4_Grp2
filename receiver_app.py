import asyncio
from typing import Tuple

from game_net_api import GameNetReceiver, Packet

class ReceiverApp:
    def __init__(self, bind_addr: Tuple[str, int]):
        self._bind_addr = bind_addr
        self._receiver = GameNetReceiver("Receiver")

    async def run(self, duration: float):
        """Run the receiver for a specified duration."""
        await self._receiver.listenOnce(self._bind_addr, self._deliver_packet)
        await asyncio.sleep(duration)
        self._receiver.stop()

    def _deliver_packet(self, packet: Packet):
        print(packet)

    def get_metrics(self):
        return self._receiver.reliable_channel_metrics, self._receiver.unreliable_channel_metrics
