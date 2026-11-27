# 测试与故障排查

| 要验证什么 | 仓库中的结果 | 适用范围 |
| --- | --- | --- |
| 九种入口能否转发、拒绝错误凭据 | [隔离协议测试](../reports/all-protocols-local.json) | 本机容器网络，含 TCP、UDP、重启和恢复 |
| 自动组能否切换和恢复 | [切换测试](../reports/client-policy-local.json) | 两个本地入口，包括全部不可用时的行为 |
| 协议在不同网络条件下表现如何 | [短流基线](../reports/baseline.json) · [分方向测试](../reports/directional.json) | 固定大小传输，分别模拟延迟、丢包和限速。公网吞吐需在目标网络测量 |
| 手机配置能否解析和转发 | [客户端记录](../reports/mobile-v33-20261031.json) | 维护电脑上的隔离客户端。蜂窝网络和手机系统接管仍需在设备上测试 |

报告对应各自记录的核心版本、环境和日期。全新云主机安装、DNS 授权、真实证书签发和防火墙恢复需要在目标 VPS 上验证。

## 本地复测

在源码目录执行。组件测试使用 Python 3.12。协议和切换测试还需要 Docker Engine、Compose 和可下载的固定镜像。为每次实验选择新的状态目录。

```bash
python3 scripts/run-tests.py --report /tmp/proxy-unit-tests.json
python3 scripts/manage.py local-test --state /tmp/proxy-protocols
python3 scripts/test-failover-local.py --state /tmp/proxy-failover
```

组件测试输出会标出跳过项。设置 `JP_DOCKER_TEST=1` 可启用 Docker 测试；加密备份和 ACME 工具检查另需 `JP_AGE`、`JP_AGE_KEYGEN` 和 `JP_LEGO`。[测试入口](../scripts/run-tests.py) · [CI 模板](../ci/README.md)

## 从设备排查

| 现象 | 先检查 |
| --- | --- |
| 所有入口都连不上 | 域名 A 记录、云防火墙、Docker 端口映射和 `manage.py status` |
| REALITY 可用、HY2 失败 | UDP 443 是否放行，客户端是否支持 Hysteria2，证书域名是否匹配 |
| 手选能通，自动组选错或一直失败 | 导入的配置类型、`Relay` 是否选了 `Auto`、探测地址是否能经各入口访问 |
| 升级后设备连不上 | 比较当前版本的协议和凭据，查看 [恢复步骤](server-setup.md) |

验收时先固定单个入口，从实际设备分别测试 HTTPS 与 UDP，核对出口，再测一次断线重连。桌面成功后，仍需在实际使用的手机和网络上复测。
