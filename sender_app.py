import asyncio
from typing import Tuple

from game_net_api import GameNetSender


class SenderApp:
    def __init__(self, addr: Tuple[str, int], dest_addr: Tuple[str, int]):
        self._addr = addr
        self._dest_addr = dest_addr
        self._sender = GameNetSender("Sender", self._addr, self._dest_addr)

    async def run(self, rate: float, duration: float):
        """Run the sender to send packets to the dest_addr at a specified rate and duration."""
        await self._sender.start()

        # Send packets on both reliable and unreliable channels
        tasks = [
            asyncio.create_task(
                self._send_packets(
                    rate=rate,
                    is_reliable=is_reliable,
                )
            )
            for is_reliable in [True, False]
        ]

        # Use wait_for so we can cancel pending tasks when duration elapses.
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=duration)
        except asyncio.TimeoutError:
            # Cancel any pending tasks (this will raise CancelledError inside them,
            # which should interrupt awaits like semaphore.acquire())
            for t in tasks:
                if not t.done():
                    t.cancel()
            # Await cancellation to let them clean up
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            # Ensure sender timers/transports are stopped
            self._sender.stop()

    def get_metrics(self):
        return self._sender.reliable_channel_metrics, self._sender.unreliable_channel_metrics

    async def _send_packets(self, rate: float, is_reliable: bool):
        interval = 1.0 / rate
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        packet_idx = 0
        next_send = t0

        # Run until the task is cancelled by the caller (external timeout)
        while True:
            next_send += interval
            sleep_for = next_send - loop.time()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            # If cancellation requested, awaiting send will raise CancelledError
            await self._sender.send(
                f'{"reliable" if is_reliable else "unreliable"}-{packet_idx}'.encode("utf-8"),
                is_reliable,
            )
            packet_idx += 1
