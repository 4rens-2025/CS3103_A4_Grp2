import asyncio
import threading

from receiver_app import ReceiverApp
from sender_app import SenderApp


def print_metrics(sender_metric, receiver_metric, duration_s: float = 1.0):
    """
    Print summarized metrics for a specific channel.
    """
    sent_packets = sender_metric.get("sent_packets", 0)
    received_packets = receiver_metric.get("received_packets", 0)
    skipped_packets = receiver_metric.get("skipped_packets", 0)
    received_bytes = receiver_metric.get("received_bytes", 0)

    delivery_ratio = (received_packets / sent_packets * 100) if sent_packets > 0 else 0.0
    throughput = (received_bytes) / (duration_s)  # bytes per second

    avg_latency = (
        receiver_metric.get("latency_sum_ms", 0.0) / received_packets if received_packets > 0 else 0.0
    )
    jitter = receiver_metric.get("jitter_ms", 0.0)
    latency_min = receiver_metric.get("latency_min_ms", 0.0)
    latency_max = receiver_metric.get("latency_max_ms", 0.0)

    print("--------------------------------------------------")
    print(f"Sent packets:       {sent_packets}")
    print(f"Received packets:   {received_packets}")
    print(f"Skipped packets:    {skipped_packets}")
    print(f"Delivery ratio:     {delivery_ratio:.2f}%")
    print(f"Throughput:         {throughput:.2f} Byte/s")
    print(f"Latency (avg):      {avg_latency:.2f} ms")
    print(f"Latency (min/max):  {latency_min:.2f} / {latency_max:.2f} ms")
    print(f"Jitter (RFC3550):   {jitter:.2f} ms")
    print("--------------------------------------------------\n")


async def main():
    receiver_addr = ("127.0.0.1", 50000)
    sender_addr = ("127.0.0.1", 50001)

    receiver_app = ReceiverApp(receiver_addr, sender_addr)
    sender_app = SenderApp(sender_addr, receiver_addr)

    send_rate = 100.0  # packets per second
    test_duration = 30.0  # seconds

    def start_receiver_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(receiver_app.run(test_duration))

    def start_sender_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(sender_app.run(send_rate, test_duration + 5.0))

    # Start receiver and sender in separate threads
    t1 = threading.Thread(target=start_receiver_loop)
    t2 = threading.Thread(target=start_sender_loop)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Get and print metrics
    sender_reliable_metric, sender_unreliable_metric = sender_app.get_metrics()
    receiver_reliable_metric, receiver_unreliable_metric = receiver_app.get_metrics()
    print("Sender and receiver stopped. Exiting.\n")

    print(f"Metrics Summary: (Packet rate: {send_rate} packets/sec over {test_duration} seconds)")
    print("===============================================")
    print("Unreliable Channel Metrics:")
    print_metrics(sender_unreliable_metric, receiver_unreliable_metric)
    print("Reliable Channel Metrics:")
    print_metrics(sender_reliable_metric, receiver_reliable_metric)


if __name__ == "__main__":
    asyncio.run(main())
