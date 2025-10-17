#!/usr/bin/env bash
set -euo pipefail

IF=lo

# remove qdisc (removes classes/filters/netem)
sudo tc qdisc del dev "$IF" root 2>/dev/null || true

echo "netem removed from $IF"
