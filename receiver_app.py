import asyncio
import time
from typing import Tuple

from game_net_api import GameNetReceiver

class ReceiverApp:
    def __init__(self, addr: Tuple[str, int], src_addr: Tuple[str, int]):
        self._addr = addr
        self._src_addr = src_addr
        self._receiver = GameNetReceiver("Receiver", self._addr, self._src_addr, self._print_packet)

    async def run(self, duration: float):
        """Run the receiver for a specified duration."""
        await self._receiver.start()
        await asyncio.sleep(duration)
        self._receiver.stop()

    def get_metrics(self):
        return self._receiver.reliable_channel_metrics, self._receiver.unreliable_channel_metrics

    def _print_packet(
        self, seq: int, is_reliable: bool, retrans_count: int, payload: bytes, arrival_timestamp: int, latency: int
    ):
        arrival_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(arrival_timestamp / 1000.0))
        channel_str = "Reliable" if is_reliable else "Unreliable"
        try:
            text = payload.decode("utf-8")
        except Exception:
            text = repr(payload)
        print(
            f"[Receiver] seq={seq}, channel={channel_str}, retransmissions={retrans_count}, arrival_time={arrival_str}, RTT(one-way)={latency}ms, payload={text} "
        )
