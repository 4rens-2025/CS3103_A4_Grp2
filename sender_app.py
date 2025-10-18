import asyncio
from typing import Tuple

from game_net_api import GameNetSender


class SenderApp:
    def __init__(self, addr: Tuple[str, int]):
        self.addr = addr
        self.sender = GameNetSender("Player 2", self.addr)

    async def run(self, receiver_addr: Tuple[str, int], rate: float, duration: float):
        await self.sender.start()
        tasks = [
            asyncio.create_task(
                self.send_packets(
                    dest=receiver_addr,
                    rate=rate,
                    duration=duration,
                    reliable=reliable,
                )
            )
            for reliable in [True, False]
        ]
        await asyncio.gather(*tasks)
        await self.sender.stop()

    def get_metrics(self):
        return self.sender.reliable_channel_metric, self.sender.unreliable_channel_metric

    async def send_packets(self, dest: Tuple[str, int], rate: float, duration: float, reliable: bool):
        interval = 1.0 / rate
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        packet_idx = 0
        next_send = t0

        while loop.time() < t0 + duration:
            next_send += interval
            sleep_for = next_send - loop.time()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            await self.sender.send(
                f'{"reliable" if reliable else "unreliable"}-packet-{packet_idx}',
                reliable=reliable,
                dest=dest,
            )
            packet_idx += 1
