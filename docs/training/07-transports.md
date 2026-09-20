# 07 · AnyTLS、Trojan 与 VLESS 的三种 HTTP 传输

**目标：** 分辨代理协议与承载方式，避免把名字当作速度等级。**前置：** 03。

| 入口 | 本仓库组合 | 必须对应的参数 | 特别观察 |
| --- | --- | --- | --- |
| AnyTLS | AnyTLS / TLS / TCP | 密码、SNI、证书 | 会话复用、填充与空闲连接 |
| Trojan | Trojan / TLS / TCP | 密码、SNI、证书 | TLS 后认证与目标连接 |
| VLESS WS | VLESS / WebSocket / TLS / TCP | UUID、路径、SNI | Upgrade 与消息封装 |
| VLESS gRPC | VLESS / gRPC / HTTP/2 / TLS / TCP | UUID、服务名、SNI | 流控与连接复用 |
| VLESS XHTTP | VLESS / XHTTP packet-up / TLS | UUID、路径、mode、SNI | 上传分包与请求调度 |

AnyTLS 的会话复用和填充策略影响连接与字节形态，不等于保证某条线路更快。参考 [AnyTLS 协议](https://github.com/anytls/anytls-go/blob/main/docs/protocol.md)。Trojan 在 TLS 之后携带认证与代理请求；参考 [Trojan 协议](https://trojan-gfw.github.io/trojan/protocol)。

WS、gRPC、XHTTP 是不同的承载安排。本仓库仅验收列出的具体组合，未把 CDN、反代、额外复用选项混入实验。`xudp` 是代理 UDP 的编码/承载能力之一，出现在节点名称里不意味着外层不再使用 TCP。

## XHTTP 特别容易发生版本拼接

上游的 [XHTTP 说明](https://xtls.github.io/config/transports/xhttp.html) 描述多种模式与部署形态。本项目选定 Mihomo 1.19.31 支持的 `packet-up`，没有为它套用 REALITY 的 Vision flow。不要直接复制另一核心的 `extra` 或 `downloadSettings` 等字段。

本地短流基线中 XHTTP 上传明显低于其他入口，说明这个具体模式/实现的额外请求组织成本值得研究；它不证明真实线路上其他 TCP 入口约 1 Mbps 下载由 XHTTP 导致。

## 独立验收

```bash
python3 scripts/manage.py local-test --state /tmp/relay-http-new --protocols anytls trojan ws grpc xhttp
```

把一条 WS 的路径故意写错，只在隔离实验中观察失败；还原后确认恢复。错误路径、错误密码、TLS 错误应分别定位。生产测速不要把五个协议一起命名后得出五个独立结论。

检查点：所有 TLS/TCP 入口下载都慢而 QUIC 较快时，优先寻找公共的 TCP 路径/发送行为与测速条件，而非宣称这五种认证机制同时坏了。继续：[Shadowsocks](08-shadowsocks.md)。
