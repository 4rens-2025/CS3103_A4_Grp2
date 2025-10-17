import asyncio
from typing import Tuple

from game_net_api.receiver import GameNetReceiver
from game_net_api.sender import GameNetSender
import random


def print_received_packet(app_name: str, addr: Tuple[str, int], seq: int, ch: int, payload: bytes):
    """Print log for each received packet."""
    try:
        text = payload.decode("utf-8")
    except Exception:
        text = repr(payload)
    print(f"[{app_name}] from={addr} seq={seq} ch={ch} payload={text}")


def print_metrics(sender_metric, receiver_metric):
    sent_packets = sender_metric["sent_packets"]
    received_packets = receiver_metric["received_packets"]

    delivery_ratio = received_packets / sent_packets * 100 if sent_packets > 0 else 0.0

    print(
        f"Sent packets: {sent_packets}, Received packets: {received_packets}, Delivery ratio: {delivery_ratio:.2f}%"
    )


async def main():
    # Start the receiver
    receiver_addr = ("127.0.0.1", 50000)
    receiver = GameNetReceiver(
        "Player 1",
        receiver_addr,
        deliver_cb=lambda addr, seq, ch, payload: print_received_packet(
            "Player 1", addr, seq, ch, payload
        ),
    )
    await receiver.start()

    # Start the sender
    sender_addr = ("127.0.0.1", 50001)
    sender = GameNetSender("Player 2", sender_addr)
    await sender.start()

    reliable_curr = unreliable_curr = 0
    for _ in range(100):
        # reliable = random.choice([True, False])
        reliable = True
        await sender.send(
            f"packet-{reliable_curr if reliable else unreliable_curr}",
            reliable=reliable,
            dest=receiver_addr,
        )

        if reliable:
            reliable_curr += 1
        else:
            unreliable_curr += 1

    await asyncio.sleep(2)

    # Clean up
    sender_unreliable_metric, sender_reliable_metric = await sender.stop()
    receiver_unreliable_metric, receiver_reliable_metric = await receiver.stop()
    print("Sender and receiver stopped. Exiting.")

    print_metrics(sender_unreliable_metric, receiver_unreliable_metric)
    print_metrics(sender_reliable_metric, receiver_reliable_metric)


if __name__ == "__main__":
    asyncio.run(main())
