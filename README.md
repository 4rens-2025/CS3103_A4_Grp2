# CS3103_A4_Grp2
CS3103 Assignment 4 - Project Group 2

Command to simulate packet loss and delay
Aware that this is applied to all network in the linux system (For testing purposes)
```sh
# add 200 ms delay + 5% loss on loopback
sudo tc qdisc add dev lo root netem delay 200ms 20ms loss 5%

# when finished, remove it
sudo tc qdisc del dev lo root
```