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

## VM environment
We provided a `VagrantFile` that provisions a VM using `VirtualBox` for you to test the custom protocol in a sandbox environment.

## Running analysis and plotting charts
In the `analysis/` folder, there are 2 scripts for running automated simulation and collects the metrics for analysis. 
- Run the simulation via `run_analysis.sh`, which will collect metrics used for analysis in `results.csv`
- Run `python3 plot_results.py` to plot the charts of the results