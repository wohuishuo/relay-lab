# 协议与端口

个人节点可配置九种入口。默认在同一个端口号上启用两种传输：REALITY 接收 TCP，Hysteria2 接收 UDP。两者可以同时监听。表中的 TCP/UDP 指客户端到 VPS 的连接方式。

| 配置 ID | 协议与传输 | 公网 → 容器端口 | 选用理由与条件 |
| --- | --- | --- | --- |
| `reality` | VLESS REALITY / Vision | TCP 443 → 14443 | 默认 TCP 入口，适合 UDP 受限的网络。客户端需要对应公钥和 SNI |
| `hy2` | Hysteria2 / QUIC | UDP 443 → 14443 | 默认 UDP 入口，可与 REALITY 互为备用。需要 UDP 可达和有效域名证书 |
| `anytls` | AnyTLS / TLS | TCP 8443 → 18443 | 给支持 AnyTLS 的客户端增加一条密码认证的 TLS 入口 |
| `tuic` | TUIC v5 / QUIC | UDP 8443 → 18443 | 支持原生 UDP 转发。需要客户端支持 v5、UDP 可达 |
| `trojan` | Trojan / TLS | TCP 9443 → 19443 | 可复用客户端的 Trojan 支持，使用密码与域名证书 |
| `ss` | Shadowsocks AEAD | TCP、UDP 8388 → 18388 | 不依赖域名证书或额外插件。两端需使用相同的 `chacha20-ietf-poly1305` 和密码 |
| `xhttp` | VLESS / XHTTP / TLS | TCP 10443 → 20443 | 适配支持 XHTTP 的客户端。两端须匹配路径和 `packet-up` 模式 |
| `ws` | VLESS / WebSocket / TLS | TCP 11443 → 21443 | 适配 WebSocket 客户端或支持 Upgrade 的反向代理。默认路径为 `/proxy-ws` |
| `grpc` | VLESS / gRPC / TLS | TCP 12443 → 22443 | 适配 gRPC 客户端和 HTTP/2 转发环境。服务名为 `proxygrpc` |

在 `settings.json` 的 `protocols` 中填入所需 ID。生成器只为启用项发布 IPv4 端口，云防火墙需放行相同的端口和传输。可选 HTTPS 订阅另用 TCP 2087。Docker 发布端口还受宿主机转发规则影响。[配置生成器](../jp/config.py) · [客户端示例](../templates/clients/reality.example.yaml)

协议选择取决于客户端支持和实际网络。先分别验证 TCP 和 UDP 两条默认入口，再决定是否加入备用组。[隔离测试结果](evidence.md)
