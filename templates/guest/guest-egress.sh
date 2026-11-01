#!/bin/sh
set -eu
user=relay-guest
if iptables -w -C OUTPUT -m owner --uid-owner "$user" -j RELAY_GUEST_OUT 2>/dev/null; then
  iptables -w -C RELAY_GUEST_OUT -j REJECT
else
  iptables -w -N RELAY_GUEST_OUT 2>/dev/null || iptables -w -F RELAY_GUEST_OUT
  iptables -w -A RELAY_GUEST_OUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
  iptables -w -A RELAY_GUEST_OUT -d 127.0.0.1 -p tcp --dport 18767 -j ACCEPT
  for proto in udp tcp; do iptables -w -A RELAY_GUEST_OUT -d 127.0.0.53 -p "$proto" --dport 53 -j ACCEPT; done
  iptables -w -A RELAY_GUEST_OUT -m addrtype --dst-type LOCAL -j REJECT
  for net in 0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.0.0.0/24 192.0.2.0/24 192.168.0.0/16 198.18.0.0/15 224.0.0.0/4 240.0.0.0/4; do iptables -w -A RELAY_GUEST_OUT -d "$net" -j REJECT; done
  iptables -w -A RELAY_GUEST_OUT -p tcp -m multiport --dports 80,443 -j ACCEPT
  iptables -w -A RELAY_GUEST_OUT -j REJECT
  iptables -w -I OUTPUT 1 -m owner --uid-owner "$user" -j RELAY_GUEST_OUT
fi
ip6tables -w -C OUTPUT -m owner --uid-owner "$user" -j REJECT 2>/dev/null || ip6tables -w -I OUTPUT 1 -m owner --uid-owner "$user" -j REJECT
