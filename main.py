import asyncio
from typing import Tuple

from game_net_api import GameClient, GameServer

SERVER_BIND = ("127.0.0.1", 9999)


def server_handler(addr: Tuple[str, int], seq: int, ch: int, payload: bytes):
    """Print log for each received packet."""
    try:
        text = payload.decode("utf-8")
    except Exception:
        text = repr(payload)
    print(f"[GameServer] from={addr} seq={seq} ch={ch} payload={text}")


async def main():
    # Start the server
    server = GameServer(SERVER_BIND, deliver_cb=server_handler)
    await server.start()

    # Start the client
    client = GameClient(("127.0.0.1", 0))
    await client.start()

    # Send 10 messages from client to server
    for i in range(10):
        await client.send(f"hello-{i}", reliable=False, dest=SERVER_BIND)

    # Sleep a bit to allow packets to be processed
    await asyncio.sleep(0.5)

    # Clean up
    sent_packets = await client.stop()
    received_packets = await server.stop()
    print("Client and server stopped. Exiting.")

    delivery_ratio = received_packets / sent_packets * 100
    print(
        f"Sent packets: {sent_packets}, Received packets: {received_packets}, Delivery ratio: {delivery_ratio:.2f}%"
    )


if __name__ == "__main__":
    asyncio.run(main())
