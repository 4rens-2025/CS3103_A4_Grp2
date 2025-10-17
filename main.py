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


async def _send_packets_worker(
    sender: GameNetSender, dest: Tuple[str, int], rate: float, duration: float, reliable: bool
):
    interval = 1.0 / rate

    loop = asyncio.get_running_loop()
    t0 = loop.time()

    next_send = t0
    packet_idx = 0

    while loop.time() < t0 + duration:
        next_send += interval
        sleep_for = next_send - loop.time()
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)

        await sender.send(
            f"{"unreliable" if not reliable else "reliable"}-packet-{packet_idx}",
            reliable=reliable,
            dest=dest,
        )
        packet_idx += 1


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

    # Start sending packets from sender to receiver
    send_rate = 100.0  # packets per second
    test_duration = 30.0  # seconds

    tasks = [
        asyncio.create_task(
            _send_packets_worker(
                sender,
                dest=receiver_addr,
                rate=send_rate,
                duration=test_duration,
                reliable=reliable,
            )
        )
        for reliable in [False, True]
    ]

    await asyncio.gather(*tasks)

    # Clean up
    sender_reliable_metric, sender_unreliable_metric = await sender.stop()
    receiver_reliable_metric, receiver_unreliable_metric = await receiver.stop()
    print("Sender and receiver stopped. Exiting.\n")

    print(f"Metrics Summary: (Packet rate: {send_rate} packets/sec over {test_duration} seconds)")
    print("===============================================")
    print("Unreliable Channel Metrics:")
    print_metrics(sender_unreliable_metric, receiver_unreliable_metric)
    print("-----------------------------------------------")
    print("Reliable Channel Metrics:")
    print_metrics(sender_reliable_metric, receiver_reliable_metric)


if __name__ == "__main__":
    asyncio.run(main())
