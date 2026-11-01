# RelayLab

[简体中文](README.zh-CN.md) · [Русский](README.ru.md)

RelayLab runs a personal proxy on an Ubuntu VPS with Docker Compose and a pinned Mihomo core. A fresh installation starts with VLESS REALITY and Hysteria2. The optional guest website issues separate credentials with an expiry time and a shared upload/download allowance.

| I want to… | Start here |
| --- | --- |
| Install on a new VPS | [Installation guide and prerequisites](docs/quickstart.md) |
| Give a guest three days and 10 GB | [Guest website and owner dashboard](docs/guest-portal.md) |
| Update, back up or roll back a node | [Operations guide](docs/server-setup.md) |
| Choose protocols or check a connection | [Ports](docs/ports.md) · [Connection repair](docs/entry-repair-20261101.md) · [Test results](docs/evidence.md) |

After configuring the new host, preview its installation plan with `sudo bash install.sh --settings /var/lib/relay-lab/settings.json`. The installation guide lists the separate apply step. On an existing node, use the operations guide.

The personal core and the guest portal run separately. The portal uses Django accounts and a private guest Mihomo process. The owner approves requests or issues a pass directly. Prices can be displayed, and approval is manual.

[Protocol handbook](docs/training/README.md) · [Pinned dependencies](versions.lock.json) · [Security](SECURITY.md) · [License](LICENSE)
