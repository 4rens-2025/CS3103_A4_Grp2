# CS3103 Assignment 4 - Project Group 2
Hybrid Transport Protocol over UDP for Real‑Time Multiplayer Games

---
## 🚀 Run the Sender and Receiver Application
You may configure packet send rate & test duration in main.py
```sh
python3 main.py
```
---

## 🧪 Network Emulation

We use Linux `tc netem` to simulate latency, jitter, and packet loss.

### Setup scripts

```sh
chmod +x netem-setup.sh
chmod +x netem-cleanup.sh

./netem-setup.sh        # apply netem settings
./netem-cleanup.sh      # reset network
```

### ✅ Example NetEm Test Profiles

| Scenario             | Description                        | Command                           |
| -------------------- | ---------------------------------- | --------------------------------- |
| **Nominal**          | Low delay, low jitter, low loss    | `./netem-setup.sh 50ms 5ms 1%`    |
| **High latency**     | Laggy but stable link              | `./netem-setup.sh 200ms 20ms 1%`  |
| **High packet loss** | Stress test reliability logic      | `./netem-setup.sh 50ms 5ms 10%`   |
| **Extreme stress**   | Harsh conditions                   | `./netem-setup.sh 300ms 30ms 15%` |

> The script supports positional arguments: `./netem-setup.sh [delay] [jitter] [loss]`
