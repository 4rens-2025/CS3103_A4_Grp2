import asyncio
from typing import Tuple

from game_net_api.receiver import GameNetReceiver
from game_net_api.sender import GameNetSender


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
    receiver = GameNetReceiver(
        "Player 1",
        ("127.0.0.1", 9999),
        deliver_cb=lambda addr, seq, ch, payload: print_received_packet(
            "Player 1", addr, seq, ch, payload
        ),
    )
    await receiver.start()

    # Start the sender
    sender = GameNetSender("Player 2", ("127.0.0.1", 0))
    await sender.start()

    async def send_unreliable_messages():
        for i in range(10):
            await sender.send(f"hello-{i}", reliable=False, dest=("127.0.0.1", 9999))

    async def send_reliable_messages():
        for i in range(10):
            await sender.send(f"reliable-hello-{i}", reliable=True, dest=("127.0.0.1", 9999))

    await asyncio.gather(send_reliable_messages(), send_unreliable_messages())

    # Sleep a bit to allow packets to be processed
    await asyncio.sleep(0.5)

    # Clean up
    sender_unreliable_metric, sender_reliable_metric = await sender.stop()
    receiver_unreliable_metric, receiver_reliable_metric = await receiver.stop()
    print("Sender and receiver stopped. Exiting.")

    print_metrics(sender_unreliable_metric, receiver_unreliable_metric)
    print_metrics(sender_reliable_metric, receiver_reliable_metric)


if __name__ == "__main__":
    asyncio.run(main())
