# 端口与网络

| ID | 协议 | 宿主公网端口 | 容器端口 | 默认 |
|---|---|---|---|---|
| reality | VLESS RAW REALITY / Vision | TCP 443 | TCP 14443 | 开启 |
| hy2 | Hysteria2 | UDP 443 | UDP 14443 | 开启 |
| anytls | AnyTLS / TLS | TCP 8443 | TCP 18443 | 关闭 |
| tuic | TUIC v5 / TLS | UDP 8443 | UDP 18443 | 关闭 |
| trojan | Trojan / TLS | TCP 9443 | TCP 19443 | 关闭 |
| ss | Shadowsocks chacha20-ietf-poly1305 | TCP/UDP 8388 | TCP/UDP 18388 | 关闭 |
| xhttp | VLESS XHTTP packet-up / TLS | TCP 10443 | TCP 20443 | 关闭 |
| ws | VLESS WebSocket / TLS | TCP 11443 | TCP 21443 | 关闭 |
| grpc | VLESS gRPC / TLS | TCP 12443 | TCP 22443 | 关闭 |

SSH TCP 22 由宿主管理，只开放管理来源。无管理 API、匿名订阅、公开 DNS 或明文代理入口。用户后续启用的私有订阅单独使用 TCP 2087（Caddy），需云防火墙和 DOCKER-USER 同时放行，不开放 UDP 2087。DNS-01 不需要 TCP 80。可选协议没有启用就不会生成端口映射；云防火墙也必须保持关闭。

生产：IPv4 bridge/NAT，Docker 默认 iptables backend，指定用户 10001，容器内高端口。内部容器地址不可作客户端服务器地址。客户端连接 VPS 公网地址。

本地：两个 internal bridge 网络，无宿主 ports。client/probe 在 front，target 在 back，仅 server 同时连接 front/back。每个测试生成随机 nonce，目标原样响应。isolation 探针使用目标真实容器 IP 测试直连失败，不以 DNS 不解析冒充隔离。

测试 target 暴露 HTTP 18080、UDP 19000、TLS 18444，仅在 back 网络内部。真实客户端测试脚本的 HTTP/UDP 端口随机映射至 127.0.0.1，结束即删除。
