# 个人代理部署

用 Docker Compose 在 Ubuntu VPS 上运行 Mihomo。默认提供两个入口：VLESS REALITY 走 TCP 443，Hysteria2 走 UDP 443。可以在客户端逐个选择，也可以配置自动切换。

[English](README.md) · [Русский](README.ru.md)

## 安装

1. 准备全新 Ubuntu 24.04 amd64 主机、Docker Engine、Compose 插件、Git、Python 3.12 和 OpenSSL。将 Cloudflare 的 A 记录直指服务器，放行 TCP 443 和 UDP 443。
2. 把仓库克隆到 `/opt/relay-lab`。按[安装指南](docs/quickstart.md)复制两个配置文件，填写域名和 DNS 凭据，预览安装计划。
3. 执行安装，把 `/var/lib/relay-lab/client.yaml` 导入自己的 Mihomo 客户端。在 `Relay` 组里选择入口，从设备上验证连接。

## 连接与切换

![个人设备和访客分别经过各自的代理核心访问目标服务。](docs/assets/architecture.svg)

客户端选择入口，VPS 上的 Mihomo 验证凭据并转发请求。默认手动选择。要按优先级使用备用入口，导出 `fallback` 配置；要按探测延迟选择，导出 `url-test` 配置。两种普通自动配置都每 120 秒探测一次，已建立的连接可能需要重连。[自动切换设置](docs/client-selection.md)

| 手册 | 内容 |
| --- | --- |
| [协议与端口](docs/ports.md) | 九种入口的用途、选用条件和端口 |
| [内部架构](docs/architecture.md) | 一次请求经过哪些组件，配置由哪些代码生成 |
| [部署与维护](docs/server-setup.md) | 版本生命周期、续期、备份和回滚 |
| [访客访问](docs/guest-portal.md) | 发放独立凭据，设置有效期和上下行总额度 |
| [测试与排查](docs/evidence.md) | 协议验证、切换实验、原始结果和适用范围 |

[安全说明](SECURITY.md) · [上游依赖](THIRD_PARTY.md) · [MIT 许可证](LICENSE)
