# Personal Proxy Setup

Run Mihomo on an Ubuntu VPS with Docker Compose. VLESS REALITY (TCP 443) and Hysteria2 (UDP 443) are enabled by default. Optional entries are AnyTLS, TUIC v5, Trojan, Shadowsocks, and VLESS over XHTTP, WebSocket or gRPC.

Enabling all nine entries uses **seven public port numbers**: TCP 443, 8388, 8443, 9443, 10443, 11443 and 12443, plus UDP 443, 8388 and 8443. An earlier deployment also used Shadowsocks with ShadowTLS and gRPC over Hysteria2. [Port mappings and deployment notes](docs/ports.md)

[简体中文](README.zh-CN.md) · [Русский](README.ru.md)

## Install

1. Prepare a fresh Ubuntu 24.04 amd64 server with Docker Engine, Compose, Git, Python 3.12 and OpenSSL. Point a Cloudflare DNS-only A record at the server. Allow TCP and UDP 443.
2. Clone this repository into `/opt/relay-lab`. Follow the [installation guide](docs/quickstart.md) to copy the two settings files, fill in your domain and DNS credentials, and preview the plan.
3. Apply the plan and import `/var/lib/relay-lab/client.yaml` into a Mihomo client. Select an entry in the `Relay` group and check the connection from your device.

## How it works

![A personal client connects to the VPS proxy. Guests use a separate gateway and proxy.](docs/assets/architecture.svg)

The client selects an entry, the VPS authenticates it, and Mihomo forwards the request. Manual selection is the default. Export a `fallback` profile for ordered failover, or `url-test` to choose by latency. Both probe every 120 seconds. Existing connections may need to reconnect. [Client selection](docs/client-selection.md)

| Guide (Chinese) | What it covers |
| --- | --- |
| [Protocols and ports](docs/ports.md) | All nine entries, client requirements and when to use each |
| [Architecture](docs/architecture.md) | Request routing, source files and optional services |
| [Operations](docs/server-setup.md) | Deployment lifecycle, certificate renewal, backup and rollback |
| [Guest access](docs/guest-portal.md) | Separate credentials, expiration and shared upload/download quota |
| [Tests](docs/evidence.md) | Protocol checks, failover tests and the scope of the results |

[Security](SECURITY.md) · [Dependencies](THIRD_PARTY.md) · [MIT license](LICENSE)
