# 版本与配置来源

核对日期：2026-09-20。运行镜像由 MetaCubeX 发布，没有自行实现或编译代理协议。配置根据固定标签源码核对，随后进行真实握手与转发测试。

| 用途 | 固定来源 |
|---|---|
| 正式版本 | https://github.com/MetaCubeX/mihomo/releases/tag/v1.19.31 |
| 维护方镜像构建流程 | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/.github/workflows/build.yml |
| VLESS 入站及 HTTP 传输字段 | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/listener/inbound/vless.go |
| VLESS 实际服务端 | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/listener/sing_vless/server.go |
| VLESS 出站 | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/adapter/outbound/vless.go |
| Hysteria2 入站 | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/listener/inbound/hysteria2.go |
| Hysteria2 密码映射 | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/listener/sing_hysteria2/server.go |
| AnyTLS | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/listener/inbound/anytls.go |
| TUIC | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/listener/inbound/tuic.go |
| Trojan | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/listener/inbound/trojan.go |
| Shadowsocks | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/listener/inbound/shadowsocks.go |
| 证书目录限制 | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/constant/path.go |
| CA 池 | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/component/ca/config.go |
| TLS 配置装载顺序 | https://github.com/MetaCubeX/mihomo/blob/v1.19.31/hub/executor/executor.go |
| Docker 防火墙 | https://docs.docker.com/engine/network/packet-filtering-firewalls/ |
| Docker Ubuntu 安装 | https://docs.docker.com/engine/install/ubuntu/ |
| ACME challenge | https://letsencrypt.org/docs/challenge-types/ |
| lego | https://github.com/go-acme/lego/releases/tag/v5.4.1 |
| DNS provider 文档 | https://go-acme.github.io/lego/dns/ |
| age | https://github.com/FiloSottile/age/releases/tag/v1.3.2 |

## 实测揭示的配置注意事项

- `SAFE_PATHS=/certs` 是证书 bind mount 可用所必需的版本行为。没有它可能配置解析成功但入口没有启动。生产 healthcheck 因此同时检查实际监听套接字。
- 本地 CA 通过客户端容器 `SSL_CERT_FILE=/config/ca.crt` 在进程启动时加载，**不**安装到 Windows/Ubuntu 宿主信任库。保持 `skip-cert-verify=false`。不依赖启动阶段后更新的全局 CA 配置影响已创建的 QUIC TLS 配置。
- UDP 目标解析需要客户端知道目标 IP。隔离实验仅给客户端加入 target 的 hosts 映射，仍不授予 back 网络连接。
- RAW 对应原生 TCP；没有将别的核心的 `raw` 传输字段直接写入 Mihomo。WS/gRPC/XHTTP 不附带 Vision flow。
- XHTTP 固定 `packet-up` 模式和路径；没有泛化声称所有 XHTTP 模式、下载分离、CDN 或其他核心版本均兼容。
- 默认关闭 Hysteria2 带宽声明驱动的激进速率设置，未配置端口跳跃、额外混淆、ECH、mTLS 或自动更新。

## 工具和镜像锁定

版本锁记录 manifest list 摘要及 linux/amd64 子镜像摘要；运行使用 manifest list 摘要和显式 amd64 平台。Docker Hub 查询地址形如 `https://hub.docker.com/v2/repositories/metacubex/mihomo/tags/v1.19.31`。摘要并不代替协议实测。

age/lego 只从各维护方 GitHub release 下载，使用发布资产 SHA256 在执行前核对。测试辅助 Python 是 Docker Official Image，仅用于本地验收，不在 VPS 常驻。
