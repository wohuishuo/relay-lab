# 上游与许可边界

RelayLab 只编排上游核心，不自行实现代理协议、密码算法或 TLS。仓库不分发核心二进制；镜像与工具从维护者发布源按锁文件获取。

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

自有编排代码与教学文档采用仓库 MIT 许可；外部依赖保持各自许可。Mihomo 上游采用 GPL-3.0，README 还规定非关联衍生项目的命名边界，因此本项目采用中性名称 RelayLab，不暗示官方身份。任何重新打包或商业分发应核查依赖许可与对应义务，不能拿本仓库 MIT 文本替代上游许可。

教程为原创解释，引用官方来源供核对；不复制私人参考仓库内容。Google/Android 仅为课程组织方式的灵感，不构成关联或认证。
