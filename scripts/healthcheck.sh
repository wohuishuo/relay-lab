#!/bin/sh
# No parser output can enter Docker's retained health log.
set -eu
/mihomo -t -d /tmp/check -f /config/server.yaml >/dev/null 2>&1
awk '
FNR == NR { expected[$1 ":" $2] = 1; next }
$1 == "sl" { next }
{
  split($2, address, ":")
  kind = FILENAME ~ /udp/ ? "udp" : "tcp"
  if (kind == "udp" || $4 == "0A") seen[kind ":" toupper(address[2])] = 1
}
END {
  for (endpoint in expected) if (!(endpoint in seen)) exit 1
}
' /config/listeners.expected /proc/net/tcp /proc/net/tcp6 /proc/net/udp /proc/net/udp6
