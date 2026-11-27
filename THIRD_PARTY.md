# 上游依赖

Mihomo 负责代理协议和 TLS。安装程序从上游下载镜像和工具，版本与校验值见 [versions.lock.json](versions.lock.json)。

| 依赖 | 固定基线 | 上游 |
| --- | --- | --- |
| Mihomo | 1.19.33；历史测试保留各自的版本 | [MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo/tree/v1.19.33) |
| Django、Uvicorn、websockets、WhiteNoise | 访客网站可选依赖见 [requirements-portal.txt](requirements-portal.txt) | [Django](https://www.djangoproject.com/)、[Uvicorn](https://github.com/encode/uvicorn)、[websockets](https://github.com/python-websockets/websockets)、[WhiteNoise](https://github.com/evansd/whitenoise) |
| Caddy | 2.11.4-alpine | [caddyserver/caddy](https://github.com/caddyserver/caddy) |
| Python Docker | 3.12.10-slim-bookworm | [docker-library/python](https://github.com/docker-library/python) |
| lego | 5.4.1 | [go-acme/lego](https://github.com/go-acme/lego) |
| age | 1.3.2 | [FiloSottile/age](https://github.com/FiloSottile/age) |
| Python-Markdown | 3.10.3，仅文档构建 | [Python-Markdown](https://github.com/Python-Markdown/markdown) |
| iproute2 | Debian 6.1.0-3，仅隔离 netem helper | [iproute2](https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/) |

本仓库的代码与文档使用 [MIT 许可证](LICENSE)。Mihomo 使用 GPL-3.0，其他依赖各自遵循上游许可证。
