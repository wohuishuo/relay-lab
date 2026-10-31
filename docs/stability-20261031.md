# Stability maintenance — 2026-10-31

This report describes an upgrade of one existing personal deployment. It does not certify a fresh installation, every network, or a phone's operating-system VPN integration. Identifiers and credentials are omitted.

## What changed

- The main Mihomo container and the deployment's existing SS + ShadowTLS sidecar moved from **v1.19.31 to v1.19.33**. Both use the official image pinned in `versions.lock.json`.
- Node addresses, credentials, ports, BBR, certificate validation and protocol-specific workarounds were preserved. No host reboot, SSH configuration change, or firewall expansion was made during this maintenance.
- A separate compact client policy adds `JP-STABLE → JP-AUTO`, explicit DNS policy and a small optional domestic-domain direct list. The existing subscription URL serves that policy; a credential-protected legacy route preserves the manual profile.
- A server timer collects resource counters about once a minute. Its JSONL history is bounded to **five files of 2 MiB each**, plus a small latest snapshot. It does not record browsing destinations, requests, tokens or packet contents, and it does not restart services automatically.
- The toolkit now attempts to restore the **current deployment being replaced** when an update command fails. It continues reporting the update as failed. This exception handler is not a substitute for an independent rollback timer if the deploy process is killed.

## Evidence and boundaries

[Sanitized machine-readable results](../reports/stability-20261031.json) preserve the individual authentication, forwarding and fallback observations. The Windows suite completed without failures; Docker-only checks and checks without their optional tool environment were skipped, as recorded in [the unit report](../reports/unit-tests.json). Live-container checks below are separate evidence.

| Check | Result | Where it ran |
|---|---|---|
| Existing server containers / OOM | Running; no recorded container OOM; no matching kernel OOM event in the examined seven-day window | Production host before upgrade |
| Current configuration against v1.19.33 | Passed | Isolated container |
| Ten configured entries: authenticated HTTPS forwarding | 10/10 passed | Isolated containers |
| Same ten entries with invalid credentials | 10/10 failed to forward | Isolated containers |
| Recreate isolated main container using v1.19.31 | Hysteria2 HTTPS forwarding passed after restoration | Isolated rollback exercise |
| Independent systemd timer | Executed its probe without an attached SSH session | Production host; harmless probe |
| Upgrade acceptance: HTTPS + UDP DNS | 10/10 passed both checks | Production host, through the actual published listeners |
| Existing v1.19.31 client against upgraded server | HY2, TUIC and gRPC-over-HY2 passed verified HTTPS | Maintenance computer's current network |
| Subscription delivery | New and legacy profiles returned verified HTTPS 200 with matching contents; invalid routes returned 404 | Staging, production host, then maintenance computer |
| Auto, accelerated lab setting | New requests recovered through TUIC at the sampled 7.609-second point after HY2 packets were deliberately dropped | Isolated local client; 5 s probes / 2.5 s timeout |
| Auto, published setting and v1.19.31 client | New requests recovered through TUIC at the sampled 30.875-second point | Isolated local client; 30 s probes / 6 s timeout |
| Encrypted backup | Download hash matched; local decryption and archive contents verified | Host and maintenance computer |
| Actual phone DNS / IPv6 / WebRTC behavior | **Not verified** | Requires that device and its active VPN profile |

The ten entries are REALITY, HY2, AnyTLS, TUIC, Trojan, SS + ShadowTLS, XHTTP, WebSocket, gRPC over HY2, and direct gRPC. The latter two share the gRPC protocol. Tests carry small requests; they are not throughput benchmarks or long-duration availability measurements.

The first chain test failed when the isolated Hysteria2 entry was asked to connect back into its own container. Removing the private-network rejection alone did not fix that fixture. The same gRPC settings worked directly, the existing production chain worked from the maintenance computer, and the staged chain passed when its gRPC destination was a separate container. The final test's narrow private-address exception existed only in the lab copy. Production's private-network rejection rules were preserved. No upstream regression or precise internal loopback mechanism is claimed from this evidence.

## The TCP failure was not repaired by adding inbound rules

During a direct SSH attempt, a bounded host capture observed the client's SYN arriving and the server transmitting and retransmitting SYN-ACK. No completed handshake followed. On the same client network, HY2 and TUIC forwarded HTTPS, while direct REALITY and SS TCP connections failed. All entries forwarded successfully from the host itself.

This localizes that observed failure to the handshake return path or client receipt, rather than to proxy authentication or a missing server TCP listener. It does **not** identify a particular carrier, government system, local app, or cloud egress rule. The kernel's capture point also does not prove that every packet reached the client. Reopening more inbound ports is not evidence-based remediation for that observation.

The published automatic policy prioritizes the working UDP transports. All entries still share one host and IP. Protocol fallback cannot survive every shared IP/path/host failure. A second independent route or node would be a separate design decision; no resource was purchased.

## Generate the compact client profile

Use an existing JSON-formatted profile exported by this project. JSON is also valid YAML; neither credentials nor generated profiles belong in Git.

```bash
python3 scripts/export-stable.py \
  --input /private/current-client.json \
  --output /private/stable-client.yaml \
  --balanced
```

Omit `--balanced` to omit the domestic-domain exceptions. `--direct-domain example.cn` adds an explicit suffix. The list is visible in `jp/client_policy.py`; it is not a claim to recognize every domestic app or CDN. There is no automatic `DIRECT` fallback for unknown traffic.

The generator preserves existing node credentials and dialer chains, excludes dependent chains from the automatic group, checks for cycles and rejects disabled certificate verification. It keeps manual choices available. It deliberately does not set a desktop TUN configuration on a mobile client.

### DNS and privacy

- Unknown-domain DNS uses DoH **through `JP-AUTO`**. No direct fallback resolver is configured for those queries.
- Node bootstrap and explicitly direct domains use separate, certificate-verified encrypted resolvers. Local LAN names use the system resolver intentionally.
- Actual TXT queries succeeded through both the proxied and explicit direct DNS policies. This is functional validation, not a packet-capture proof covering every application on the phone.
- `ipv6: false` controls the core's IPv6 behavior. It does not by itself disable or intercept every IPv6 route of the device's operating system.
- A system HTTP proxy alone does not capture arbitrary UDP/STUN traffic. WebRTC requires checking the active browser and full-device VPN capture. Blanket STUN blocking can break calls and still does not cover every possible STUN port; it is not enabled here.
- A domain deliberately routed `DIRECT` exposes the ordinary network egress to that service. A VPN cannot simultaneously bypass a service and conceal that bypass from it.

The subscription is configuration distribution. It cannot make a disconnected phone switch unless its client already has the profile and performs the checks. A server-side probe cannot measure the phone-to-node path.

## Update and recovery

The live update copied the current release, preserved its runtime configuration, validated the new image, verified an encrypted backup, and cached both old and new images before the cutover. An independent systemd timer was armed before replacement. Failed deployment or failed host acceptance invoked restoration immediately; lack of confirmation would restore the captured old release after five minutes. Confirmation followed successful host and external checks, then the timer was disarmed.

The subscription used a separate rollback window and content checks. Its temporary validation-container failure was an `exec EPERM`: the official Caddy binary carries a file capability. Matching the existing production container's minimal `NET_BIND_SERVICE` capability and writable temporary directory fixed the test container; no privileged container was enabled.

Replacing one core can interrupt existing connections. Keeping credentials allows compatible clients to reconnect; it does not migrate a TCP session or QUIC stream between protocols. The observed fallback timings are individual trials, not latency guarantees. **99.9999% annual availability permits about 31.5 seconds of total downtime per year**; these tests and one VPS cannot establish that availability level.

## Resource monitoring

Run one collection on the Linux host, outside the source tree:

```bash
sudo python3 scripts/server-metrics.py --state /var/lib/relay-lab/metrics
sudo python3 scripts/server-metrics.py --state /var/lib/relay-lab/metrics --show
```

Schedule the first command with a systemd oneshot/timer if continuous history is wanted. Use a root-owned state directory, `UMask=0077`, a bounded runtime and memory limit, and a read-only service filesystem except for that directory. The existing deployment has this timer installed. Its installation path retains the older `jp-proxy` directory naming; a new quickstart uses `relay-lab`. Adjust paths to the actual installation.

Samples include container health, restart and OOM counts, cgroup memory, individual process RSS/swap/FD/thread counts, host available memory, disk space, interface byte/drop counters and conntrack utilization. Measuring the child process avoids mistaking Docker's tiny init process for the proxy core. RSS and cgroup memory are different accounting measures; shared executable pages can make their values differ. Interface counters include host traffic and are not a monthly billing meter.

Sustained growth under comparable workload warrants investigation. A high single RSS measurement, cache retention or old swap usage does not prove a leak. Routine reboots are not used to hide a trend. Host OS updates and a requested kernel reboot are separate maintenance work; this upgrade did not reboot the host.

## Interface and IP reputation

Mihomo is a headless core. MetaCubeXD is a compatible frontend, not evidence that a public management API is needed. No public controller was enabled in this maintenance. Use a private, authenticated management channel for such a panel.

Certificate validation, authentication, restricted administration and bounded logs improve security. They do not turn a hosting-provider address into a residential address, erase IP reputation, or guarantee that traffic will not be classified as VPN or automation. No blanket claim of “clean IP”, “undetectable VPN”, or phone-wide leak protection is made.

## Primary references

- [Mihomo v1.19.33 release and fixes](https://github.com/MetaCubeX/mihomo/releases/tag/v1.19.33)
- [Mihomo DNS configuration](https://wiki.metacubex.one/config/dns/)
- [Mihomo fallback groups](https://wiki.metacubex.one/config/proxy-groups/fallback/)
- [Mihomo TUN configuration](https://wiki.metacubex.one/config/inbound/tun/)
- [MetaCubeXD](https://github.com/MetaCubeX/metacubexd)
- [Akamai LISH recovery console](https://techdocs.akamai.com/cloud-computing/docs/access-your-system-console-using-lish)
