# 11 · Docker、端口与可恢复部署

**目标：** 知道发布端口经过什么防火墙，并能安全回退。**前置：** 02、10。

## 网络模式是安全设计的一部分

生产使用 Docker bridge 和逐项端口发布，不使用 host network。容器内监听端口与公网端口不同，详见[端口表](../ports.md)。核心非 root、只读根文件系统、去掉全部 capabilities，不挂载 Docker socket，不公开管理 API。

Docker 的发布流量经过 NAT/转发，可能绕开 UFW 普通 INPUT 链。默认 iptables backend 应在 DOCKER-USER 等正确位置管理转发；nftables backend 需要对应规则，不能复制另一后端的命令。不要通过关闭 Docker 防火墙管理来“修复”连通性。参见 [Docker 官方防火墙说明](https://docs.docker.com/engine/network/packet-filtering-firewalls/)。

## 云防火墙怎么填

| 字段 | 含义 |
| --- | --- |
| Label | 便于辨认的名字，例如 reality-tcp |
| Action | 必要入口选 Accept |
| Protocol / Port | 按端口表精确选择 TCP 或 UDP |
| Sources | SSH 仅管理员来源 CIDR；代理入口按用户范围 |

默认入站 Drop；出站满足 DNS、时间同步、ACME、镜像下载与代理目标访问需要。不要只准出站 443 后还期望代理任意端口。ICMP/ICMPv6 与 PMTU 有关，不能把一切控制报文盲目禁掉。

修改 SSH 或防火墙前，必须保留原会话、验证第二条登录会话、实际进入云恢复控制台，并准备定时恢复旧规则。Lish/控制台属于管理恢复通路；它不是本机 `localhost`。向导不代替你修改这些规则。

## 发布与回滚

`prepare` 生成新 release；`validate` 检查配置与证书；`deploy` 检查容器和监听。最后仍需真实客户端逐入口正负认证验收。失败时停止候选服务并返回非零，不能把“容器存在”打印成成功。

成功升级后可 `rollback` 回到上一个成功 release。**失败升级后 current 仍是旧版本，要重新 deploy 旧 current，而不是误回滚到更早的 previous。** 已撤销凭据的版本禁止恢复。

## 本地练习

跑完整 `local-test`，查看所有监听共存、重启、1.19.30/1.19.31 替换结果。它模拟的是核心生命周期，不能替代 Ubuntu 云主机防火墙、SSH 或整机重启验收。

检查点：Docker `healthy` 只证明预期监听存在；一个监听着但认证全失败的进程仍可能健康。生产必须另有端到端探针。继续：[订阅与切换](12-subscriptions.md)。
