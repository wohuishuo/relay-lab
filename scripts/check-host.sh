#!/usr/bin/env bash
set -Eeuo pipefail
printf '=== Host resources ===\n'
free -h
df -h /
df -i /
printf '\n=== Container usage ===\n'
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}'
docker system df
printf '\n=== Listening ports ===\n'
ss -lntup
printf '\n=== Docker firewall backend and rules (read only) ===\n'
if command -v iptables >/dev/null; then
  iptables -S DOCKER-USER || true
fi
printf '\n=== Memory pressure / OOM ===\n'
journalctl -k --since '24 hours ago' --no-pager | grep -Ei 'out of memory|oom-kill|killed process' || true
printf '\n=== Journal capacity ===\n'
journalctl --disk-usage
printf '\nInterface counters reset on reboot; use cloud billing for monthly allowance.\n'
cat /proc/net/dev
