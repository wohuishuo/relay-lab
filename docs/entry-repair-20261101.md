# 11 月 1 日节点连接修复

原订阅里的 REALITY、AnyTLS、Trojan、Shadowsocks、XHTTP 和 WebSocket 现在优先经自有 TUIC 连接日本服务器，备用入口为自有 HY2。每个节点仍然执行自己的协议握手和认证。原 `JP-GRPC` 继续经 HY2，原 `JP-GRPC-DIRECT` 保留用于测试直连，新增 `JP-GRPC-RECOVERED` 经修复入口连接 gRPC。

六个以 `-DIRECT` 标记的对照项保留原生 TCP 配置。原 `JP-AUTO` 的顺序和实际候选传输与更新前相同，`JP-STABLE` 的默认选择仍为 `JP-AUTO`。原生 TCP 路径在受测网络上仍然超时。两个 QUIC 入口与各协议共享一台主机，可能同时中断。

## 为什么调整第一跳

在同一公网 HTTPS 端口做两次连接，Linode 网卡只采集限定来源的 TCP 包头。直连样本有 3 个 SYN 和 7 个 SYN-ACK，未看到完成握手的 ACK。参照服务商出口的样本有 1 个 SYN、1 个 SYN-ACK 和匹配的 ACK，并收到了预期的 HTTPS 404。IPv6 测试在这次窄过滤窗口中没有看到匹配的 SYN。容器当前只发布 IPv4 端口。抓包能定位到这次握手阶段，无法识别具体丢包设备。

## 验收和回滚

- v1.19.31 对七个修复入口逐项检查了 HTTPS 和 UDP DNS。对每个入口单独替换错误凭据后均无法转发，同路径正确凭据的对照请求成功。
- 隔离丢包实验中，TUIC 中断后在 33.7 秒的采样点经 HY2 恢复，七个入口均经备用入口取得 204。两个入口均丢包时测试请求失败。这个时间只描述本轮实验。
- v1.19.33 使用经验证的 HTTPS 重新下载实际发布的订阅。七个修复入口分别下载 31,892 字节的同一文件，全部匹配上游固定版本的 Git blob 哈希。
- v1.19.32 桌面端使用本地控制管道热加载，保留当前全局选择。在更新前已建立的同一条 TLS 连接上再次取得预期响应。手机系统尚待实机验收。
- 发布只原子替换受保护的订阅文件。独立回滚计时器在外部验收通过后解除，服务端三个容器保持原启动时间。本机加密备份已用原身份解密并比对原文。

[逐项测试数据](../reports/entry-repair-20261101.json) · [单元检查](../reports/entry-repair-unit-20261101.json) · [Mihomo 第一跳代理说明](https://wiki.metacubex.one/config/proxies/dialer-proxy/)

在使用相同标准节点命名的部署中，可以从当前私有配置生成候选文件，再在目标客户端验收。

```bash
python3 scripts/export-stable.py --input /private/current.json \
  --output /private/recovered.yaml --balanced --repair-tcp
```

本次部署的手动服务端回滚入口是受保护维护目录中 `repair_publish_20261101.py rollback`。该操作校验版本指纹，用发布前的订阅原文替换当前文件，再验证 HTTPS。公开仓库只含生成逻辑和脱敏结果。
