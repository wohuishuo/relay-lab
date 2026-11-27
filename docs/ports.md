# 协议与端口

## 个人代理入口

新装只启用 `reality` 和 `hy2`。九项全部启用时，Compose 发布 **7 个端口号、10 个端口映射**：7 个 TCP、3 个 UDP。443、8388、8443 各有 TCP 和 UDP 两个映射。表中左侧是客户端应填写的 VPS 端口，右侧是容器内监听端口。

| 配置 ID | 协议与传输 | 公网 → 容器端口 | 选用理由与条件 |
| --- | --- | --- | --- |
| `reality` | VLESS REALITY / Vision | TCP 443 → 14443 | 默认 TCP 入口，适合 UDP 受限的网络。客户端需要对应公钥和 SNI |
| `hy2` | Hysteria2 / QUIC | UDP 443 → 14443 | 默认 UDP 入口，可与 REALITY 互为备用。需要 UDP 可达和有效域名证书 |
| `anytls` | AnyTLS / TLS | TCP 8443 → 18443 | 给支持 AnyTLS 的客户端增加一条密码认证的 TLS 入口 |
| `tuic` | TUIC v5 / QUIC | UDP 8443 → 18443 | 支持原生 UDP 转发。需要客户端支持 v5、UDP 可达 |
| `trojan` | Trojan / TLS | TCP 9443 → 19443 | 可复用客户端的 Trojan 支持，使用密码与域名证书 |
| `ss` | Shadowsocks（SS，AEAD） | TCP、UDP 8388 → 18388 | 不依赖域名证书或额外插件。两端需使用相同的 `chacha20-ietf-poly1305` 和密码 |
| `xhttp` | VLESS / XHTTP / TLS | TCP 10443 → 20443 | 适配支持 XHTTP 的客户端。两端须匹配路径和 `packet-up` 模式 |
| `ws` | VLESS / WebSocket / TLS | TCP 11443 → 21443 | 适配 WebSocket 客户端或支持 Upgrade 的反向代理。默认路径为 `/proxy-ws` |
| `grpc` | VLESS / gRPC / TLS | TCP 12443 → 22443 | 适配 gRPC 客户端和 HTTP/2 转发环境。服务名为 `proxygrpc` |

在 `settings.json` 的 `protocols` 中填入所需 ID。生成器只为启用项发布 IPv4 端口，云防火墙需放行相同的端口和传输。可选 HTTPS 订阅另用 TCP 2087。Docker 发布端口还受宿主机转发规则影响。[配置生成器](../jp/config.py) · [客户端示例](../templates/clients/reality.example.yaml)

协议选择取决于客户端支持和实际网络。先分别验证 TCP 和 UDP 两条默认入口，再决定是否加入备用组。[隔离测试结果](evidence.md)

## 已有部署中的其他组合

历史验收记录逐项测试了 10 个客户端条目。其中 Shadowsocks 搭配了独立的 ShadowTLS 容器；新机模板里的 `ss` 使用普通 Shadowsocks AEAD。另有两个条目都使用 gRPC：一个直接连接，一个先经过 Hysteria2。它们复用已有监听，客户端多出一个选择并不要求 VPS 再开一个端口。公开记录没有列出 ShadowTLS 的公网端口，不能把模板的 8388 当作该部署的实测值。[历史部署说明](https://github.com/wohuishuo/personal-proxy-setup/blob/434a08d6e3fef1038aed44c6ce5e63abf0941879/docs/stability-20261031.md) · [逐项验收结果](../reports/stability-20261031.json)

## 订阅、访客和本机服务

| 使用位置 | 默认端口或地址 | 用途 |
| --- | --- | --- |
| VPS 上的 Caddy（可选） | TCP 2087 → 容器 TCP 2087 | HTTPS 订阅。默认绑定回环，可另选宿主端口和绑定地址；公网访客路由可共用此端口 |
| 客户端设备 | `127.0.0.1:17890` | HTTP/SOCKS 代理，供本机应用使用 |
| 客户端设备 | `127.0.0.1:1053` | stable 和 mobile 客户端配置中的 DNS 监听 |
| 访客服务所在主机 | `127.0.0.1:18766`、`127.0.0.1:18767` | 分别是访客网站和访客 Mihomo 后端；公网请求由 Caddy 接入 |
| 管理设备 | `127.0.0.1:18769` | 管理员打开 SSH 隧道后使用的本机入口，转发至远端回环 18766 |
| Docker 实验网络 | TCP 18080、TCP 18444、UDP 19000 | 分别用于 HTTP、TLS 和 UDP 测试，仅供隔离实验 |

访客策略里出现的 TCP 80/443 是允许访问的**目标端口**。部署个人节点时，按上表所选协议放行 VPS 入站；客户端回环端口与实验端口无需对公网开放。[订阅端口映射](../compose.subscription.yaml) · [访客服务](../scripts/guest-portal.py) · [管理隧道](../portal/guest_admin.py)
