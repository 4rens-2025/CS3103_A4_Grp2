#!/usr/bin/env bash
set -euo pipefail

IF=lo
SRC=127.0.0.1
DST=127.0.0.1
SPORT=50000
DPORT=50001

# Nominal defaults
DEFAULT_DELAY="50ms"
DEFAULT_JITTER="5ms"
DEFAULT_LOSS="1%"

# Use args or defaults
DELAY="${1:-$DEFAULT_DELAY}"
JITTER="${2:-$DEFAULT_JITTER}"
LOSS="${3:-$DEFAULT_LOSS}"

# reset then add qdiscs
sudo tc qdisc del dev "$IF" root 2>/dev/null || true
sudo tc qdisc add dev "$IF" root handle 1: prio
sudo tc qdisc add dev "$IF" parent 1:1 handle 10: netem delay "$DELAY" "$JITTER" loss "$LOSS"

# filter: sender -> receiver
sudo tc filter add dev "$IF" protocol ip parent 1:0 prio 1 u32 \
  match ip src "$SRC"/32 \
  match ip dst "$DST"/32 \
  match ip sport $SPORT 0xffff \
  match ip dport $DPORT 0xffff \
  flowid 1:1

# filter: receiver -> sender
sudo tc filter add dev "$IF" protocol ip parent 1:0 prio 2 u32 \
  match ip src "$DST"/32 \
  match ip dst "$SRC"/32 \
  match ip sport $DPORT 0xffff \
  match ip dport $SPORT 0xffff \
  flowid 1:1

echo "netem enabled on $IF for $SRC:$SPORT <-> $DST:$DPORT (delay=$DELAY jitter=$JITTER loss=$LOSS)"
