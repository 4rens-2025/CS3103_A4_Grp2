import asyncio
import time
from typing import Tuple

from game_net_api import GameNetReceiver


class ReceiverApp:
    def __init__(self, addr: Tuple[str, int]):
        self._addr = addr
        self._receiver = GameNetReceiver("Receiver", self._addr, deliver_cb=self._print_packet)

    async def run(self, duration: float):
        """Run the receiver for a specified duration."""
        await self._receiver.start()
        await asyncio.sleep(duration)
        self._receiver.stop()

    def get_metrics(self):
        """Get the receiver metrics."""
        return self._receiver.reliable_channel_metric, self._receiver.unreliable_channel_metric

    def _print_packet(self, seq: int, ch: int, payload: bytes, arrival_ts: float, latency: float):
        """Callback to print received packet information."""
        arrival_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(arrival_ts / 1000))
        try:
            text = payload.decode("utf-8")
        except Exception:
            text = repr(payload)
        print(
            f"[Receiver] seq={seq} ch={ch} arrival={arrival_str} latency(one-way)={latency:.2f} ms payload={text} "
        )
