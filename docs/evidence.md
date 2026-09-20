# 验证记录与已知限制

实验执行于 2026-09-20 UTC（北京时间跨至 09-21），Windows Docker Desktop 的 Linux 容器环境。原始报告仅含实验数据，不包含真实服务器身份。当前 GitHub 项目是部署项目的脱敏副本，不包含生产状态。

## 本地已验证

| 验证 | 结果 | 证据 |
| --- | --- | --- |
| 单元与真实组件回归 | 31 项通过，0 跳过 | [unit-tests.json](../reports/unit-tests.json) |
| 九协议 TCP/UDP 正确凭据 | 每入口通过 | [all-protocols-local.json](../reports/all-protocols-local.json) |
| 九协议错误凭据 | TCP/UDP 均拒绝 | 同上 |
| TLS 负例 / REALITY 错误公钥 | 按入口类型拒绝 | 同上 |
| 目标网络隔离 | 客户端不能直连目标 IP | 同上 |
| 共存、重启、证书替换 | 通过 | 同上 |
| 服务端 1.19.30 / 1.19.31 切换 | 所有九入口逐项复测通过；客户端固定 1.19.31 | 同上 |
| SS 不使用插件 | 正确 TCP/UDP 成功，错误密码与错误加密方法失败 | [ss-local.json](../reports/ss-local.json) |
| 九协议短流基线 | 54 次传输与哈希校验通过 | [baseline.json](../reports/baseline.json) |
| 四协议方向性实验 | 96 次传输与哈希校验通过 | [directional.json](../reports/directional.json) |
| 客户端策略 | manual/fallback/url-test 转发、自动备用、全部故障不直连、恢复通过 | [client-policy-local.json](../reports/client-policy-local.json) |
| HTTPS 订阅 | 真实本机 TLS、错误 CA/域名/路径拒绝、重启、链接轮换 | 单元报告中的 test_subscription |
| age 备份 | 加密解密往返、错误身份拒绝 | 单元报告中的 test_backup |

策略实验使用两个本地 SS 入口，以 2 秒健康检查周期缩短实验；生产生成配置默认 120 秒。实验有随机密码的内部管理 API 用于观测选择，未发布宿主端口；生产与导出配置不启用此 API。该实验验证客户端机制，不是跨地域高可用测试。

## 本轮没有完成或没有执行

2026-09-21 文档更新：新增用户观察“校园 Wi-Fi 慢、SIM 下载较正常”，未收到对应原始样本，也未新增真实线路测速。补充 SS 方法/代际和校园策略机制，不把它们标成已完成的 AES/SS 2022 兼容性或性能测试。既有实验 JSON 保持原样。

- 全新 Ubuntu 云主机安装向导端到端执行、真实 DNS API/ACME、云防火墙和整机重启。
- 现有生产节点的连接、修改、重启、调参、负载测试或抓包。
- 用户设备上每个版本的 Clash Verge Rev / Clash Mi 验收。
- 真实路径慢速根因、SS 公网 TCP 失败的最终归因。
- 多日稳定性、完整渗透测试、跨故障域容灾、99.9999% SLO。
- GitHub Actions 云端执行：当前 OAuth 授权缺少 workflow 权限，[CI 模板](../ci/README.md)已保留但未启用。

安装向导另有无副作用计划、既有部署拒绝、前提缺失拒绝、ACME/部署失败停止后续阶段、成功编排顺序测试。涉及云端操作的编排测试使用替身；不能据此声称真实新机安装已经通过。阅读站点通过桌面/手机浏览器交互与视觉检查，见 [site-check.json](../reports/site-check.json)。

## 如何解释测量

基线是虚拟网络的短流实验，2 MiB 可能主要受握手/调度影响，不是长时间容量测定。方向实验改变容器出口 qdisc，同时可能影响反向 ACK；netem 随机损失不是精确模拟现实运营商。

qdisc 输出在传输前记录，不能拿其中 dropped 0 宣称没有丢包。原始 transfer 的错误类别、成功数、最小/最大/中位数分别保存；本次无传输失败，不能据此外推全天稳定。见[环境与限制](../reports/environment.json)。

## 可复现入口

```bash
python3 scripts/run-tests.py
python3 scripts/manage.py local-test --state /tmp/relay-full-new
python3 scripts/test-failover-local.py --state /tmp/relay-policy-new
```

完整组件回归需先安装锁定工具，并设置 `JP_AGE`、`JP_AGE_KEYGEN`、`JP_LEGO` 的路径；设置 `JP_DOCKER_TEST=1` 启用 Docker 回归。缺少条件时测试显示 skipped，报告为 partial，不能转述为全量通过。

按[测量课程](training/14-measurement.md)运行 benchmark。不要把 `client-test.py` 指向正在工作的服务器，除非已安排实际验收窗口。
