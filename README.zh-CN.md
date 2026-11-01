# RelayLab

[English](README.md) · [Русский](README.ru.md)

用 Docker Compose 和固定版本的 Mihomo 在 Ubuntu VPS 上运行个人代理。新机默认启用 VLESS REALITY 和 Hysteria2。可选的访客网站为每张通行证单独设置到期时间和上下行总额度。

| 我想做什么 | 入口 |
| --- | --- |
| 安装到新 VPS | [安装指南与前提](docs/quickstart.md) |
| 给朋友开三天、10 GB 的临时链接 | [访客网站与管理员工作台](docs/guest-portal.md) |
| 更新、备份或回滚个人节点 | [维护手册](docs/server-setup.md) |
| 选择协议或排查断线 | [端口表](docs/ports.md) · [连接修复记录](docs/entry-repair-20261101.md) · [测试结果](docs/evidence.md) |

新主机准备好后，用 `sudo bash install.sh --settings /var/lib/relay-lab/settings.json` 预览安装计划。正式执行的步骤见安装指南。已有节点按维护手册更新。

访客使用独立的 Mihomo 进程和凭据。网站基于 Django 的账号与管理后台，支持注册申请、人工批准、直接发放和撤销。套餐可以展示价格，开通由管理员确认。

[协议手册](docs/training/README.md) · [固定依赖](versions.lock.json) · [安全说明](SECURITY.md) · [许可证](LICENSE)
