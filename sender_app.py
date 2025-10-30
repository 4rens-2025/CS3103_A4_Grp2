import asyncio
from typing import Tuple

from game_net_api import GameNetSender


class SenderApp:
    def __init__(self, addr: Tuple[str, int]):
        self._addr = addr
        self._sender = GameNetSender("Sender", self._addr)

    async def run(self, receiver_addr: Tuple[str, int], rate: float, duration: float):
        """Run the sender to send packets to the receiver at a specified rate and duration."""
        await self._sender.start()

        # Send packets on both reliable and unreliable channels
        tasks = [
            asyncio.create_task(
                self._send_packets(
                    dest=receiver_addr,
                    rate=rate,
                    duration=duration,
                    reliable=reliable,
                )
            )
            for reliable in [True, False]
        ]
        await asyncio.gather(*tasks)

        await self._sender.stop()

    def get_metrics(self):
        return self._sender.reliable_channel_metric, self._sender.unreliable_channel_metric

    async def _send_packets(self, dest: Tuple[str, int], rate: float, duration: float, reliable: bool):
        """
        Send packets at the specified rate and duration through specific channel.

        Args:
            dest (Tuple[str, int]): Destination address.
            rate (float): Packets per second.
            duration (float): Duration to send packets in seconds.
            reliable (bool): Whether to use reliable channel.
        """
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
            await self._sender.send(
                f'{"reliable" if reliable else "unreliable"}-{packet_idx}',
                reliable=reliable,
                dest=dest,
            )
            packet_idx += 1
