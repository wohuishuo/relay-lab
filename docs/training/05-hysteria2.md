# 05 · Hysteria2：先理解 QUIC，再理解带宽参数

**目标：** 知道为何它可能更快，也知道何时会失败。**前置：** 03。

Hysteria2 在 QUIC 上提供代理请求与数据转发。客户端先建立并验证 QUIC/TLS 连接，再进行认证与请求；外层用 UDP 不代表应用 TCP 被变成不可靠传输。UDP 数据报转发和可靠流的语义应分别验收。[官方协议说明](https://v2.hysteria.network/docs/developers/Protocol/) 是机制来源。

## 当前配置究竟启用了什么

服务端 `ignore-client-bandwidth: true`，客户端没有填写 `up/down` 固定带宽。不能因此把截图中的快归因于“已经启用 Brutal 暴力发包”。固定版本 [客户端实现](https://github.com/MetaCubeX/mihomo/blob/v1.19.31/adapter/outbound/hysteria2.go) 与 [服务端实现](https://github.com/MetaCubeX/mihomo/blob/v1.19.31/listener/sing_hysteria2/server.go) 将带宽选项传给依赖，并提供 BBR 拥塞控制回调。实际协商路径与填写固定速率的方案不同。

带宽参数不是家里套餐数字的装饰。设置高于可用瓶颈会增加排队、损失和其他业务影响；设置过低可能自己造出瓶颈。调参前先测方向、负载与拥塞状态。

## 为什么截图可能出现优势

这是**待验证假设**：TCP 与 UDP 可能经过不同策略；用户态 QUIC 与系统 TCP 的拥塞行为不同；已有连接复用、端点或流数不同。任何一种都需要对照。UDP 被过滤或 NAT 状态异常时，Hysteria2 也可能完全不可用。

## 本地练习

```bash
python3 scripts/manage.py local-test --state /tmp/relay-hy2-new --protocols hy2
```

观察错误密码、错误域名与错误 CA 被拒绝。证书检查失败应修复证书或 SNI，不能关闭验证。性能实验中给下载方向 2 Mbps 限速，HY2 下载同样约 1.85 Mbps；它没有越过物理/策略容量的能力。

检查点：如果 UDP 443 未放行、TCP 443 已放行，REALITY 成功能证明 HY2 可达吗？不能。端口号相同但传输协议不同。继续：[TUIC](06-tuic.md)。
