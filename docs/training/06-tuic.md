# 06 · TUIC v5：会话、可靠流与 UDP 转发

**目标：** 区分版本、拥塞算法与 UDP relay 模式。**前置：** 03、05。

TUIC v5 基于 QUIC，以用户身份进行认证并承载 TCP 连接和 UDP 关联。协议版本不是可忽略的标签；v4 与 v5 的客户端配置和身份方式不能混用。参见 [TUIC 规范](https://github.com/tuic-protocol/tuic/blob/master/SPEC.md)。

仓库服务端与客户端都指定 `congestion-controller: bbr`，客户端指定 `udp-relay-mode: native`。用户 UUID 和密码均参与配置。TLS 证书由客户端按域名和信任链检查。

## 不要混淆两个 UDP

外层 QUIC 一定由 UDP 承载；内层用户请求可能是 TCP，也可能是 UDP。`native` 描述内层 UDP 如何转发，不能解释成“所有应用请求都不用确认”。数据报尺寸、PMTU 和 QUIC 的数据报能力会影响大 UDP 包；小 DNS 查询成功不代表所有游戏/视频 UDP 负载都成功。

固定版本实现：[TUIC outbound](https://github.com/MetaCubeX/mihomo/blob/v1.19.31/adapter/outbound/tuic.go)。配置字段参考[官方 TUIC 文档](https://wiki.metacubex.one/config/proxies/tuic/)，新增字段仍需版本核对。

## 实验与判断

```bash
python3 scripts/manage.py local-test --state /tmp/relay-tuic-new --protocols tuic
```

至少记录：正确认证 TCP、正确认证 UDP、错误认证拒绝、证书负例、重启恢复。之后才有资格讨论吞吐；尚未建立连接的“0 Mbps”是失败，不是协议很慢。

检查点：本地丢包条件下某次 TUIC 比 HY2 慢，能否说 TUIC 算法一定更差？不能。两者共享 QUIC 大类但实现、会话复用、调度、样本波动不同，需要多轮、顺序平衡与相同路径。继续：[TLS 与传输层组合](07-transports.md)。
