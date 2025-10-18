import asyncio
from typing import Tuple

from game_net_api import GameNetReceiver


class ReceiverApp:
    def __init__(self, addr: Tuple[str, int]):
        self.addr = addr
        self.receiver = GameNetReceiver("Player 1", self.addr, deliver_cb=self.print_packet)

    async def run(self):
        await self.receiver.start()
        await asyncio.sleep(35.0)  # Run for 35 seconds
        await self.receiver.stop()

    def get_metrics(self):
        return self.receiver.reliable_channel_metric, self.receiver.unreliable_channel_metric

    def print_packet(self, addr: Tuple[str, int], seq: int, ch: int, payload: bytes, rtt: float):
        try:
            text = payload.decode("utf-8")
        except Exception:
            text = repr(payload)
        print(f"[Player 1] from={addr} seq={seq} ch={ch} payload={text} rtt={rtt:.2f} ms")
