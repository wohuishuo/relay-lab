# 验收记录规则

每项只能写 PASS / FAIL / PENDING / BLOCKED，附日期、镜像摘要和客户端核心版本。解析成功不等于协议可用；TCP 通不等于 UDP 通；本机 Docker 通不等于 VPS 网络通。

## 本地自动验收

每条入口单独运行：服务端/客户端配置解析、启动、HTTP nonce 原样返回、UDP nonce 原样返回、错误凭据 TCP/UDP 均无法访问目标、正向控制恢复、服务端重启后 TCP/UDP 恢复。TLS 入口另测错误 CA 和错误域名，REALITY 另测错误公钥。每条测试均验证客户端不能直连目标 IP。

全部入口共同开启后再逐个复测；使用 1.19.30/1.19.31 服务端验证镜像切换及恢复，客户端固定 1.19.31。测试 CA 仅供实验，不上传到生产。

本地自动结果见 [验证记录](evidence.md) 和 JSON 证据。Windows Docker 的网络、文件权限和宿主防火墙不等同 Ubuntu；服务器端仍需以下验收。

## 真实服务器验收：初始全部 PENDING

| 项目 | 要求 |
|---|---|
| 镜像和主机版本 | `mihomo -v` 与锁文件相符，记录 Ubuntu/Engine/Compose 版本 |
| 每个启用入口 | 真实网络 TCP/HTTPS 下载、UDP/DNS 转发，出口是 VPS IP |
| 错误认证 | 修改客户端 UUID/密码后转发失败，恢复原凭据立即成功 |
| TLS | 无跳过验证；错误域名/不可信 CA 拒绝；证书链完整 |
| REALITY | 正确公钥通过，错误公钥无法代理；回落页面不是通过 |
| 设备兼容 | 记录每台设备的应用版本和实际内置核心版本；导入和连接均成功 |
| 外部端口检查 | 只开放选定端口；API、明文 HTTP/SOCKS、DNS 服务未对公网开放 |
| SSH 与防火墙 | 允许来源能登录、其他来源拒绝；控制台恢复可用；IPv6 无旁路 |
| 宿主重启 | 重启 VPS 后自动恢复；逐入口重新验证 |
| 更新/回滚 | 版本切换、失败恢复、旧版本回滚均重新验证 |
| 续期加载 | 新证书序列号已由实际 TLS/QUIC 客户端观察到 |
| 容量 | 正常负载内存峰值、OOM、磁盘/日志增长、UDP 丢包与吞吐 |
| 备份恢复 | 新目录/新主机恢复成功，错误解密密钥失败 |

在真实客户端电脑上，可使用导出的单入口配置进行额外自动验收：

```powershell
python scripts/client-test.py --config C:/private/reality.yaml --expected-exit-ip YOUR_VPS_IPV4
python scripts/client-test.py --config C:/private/hy2.yaml --expected-exit-ip YOUR_VPS_IPV4
```

每条可选入口都单独执行。脚本启动维护方 Mihomo 客户端，使用 curl 经代理检查 HTTPS 出口，再通过该客户端 UDP 隧道向 1.1.1.1:53 查询 example.com；随后测试错误认证和正向恢复。IP 查询服务默认 api.ipify.org，可通过 `--ip-url` 替换为返回纯文本 IP 的可信 HTTPS 服务。DNS 目标可改，外部服务异常会导致失败，不会自动改成直连。

此脚本**第一阶段不运行到远程服务器**，也不能代替实际手机 App 验收。它不自动修改系统代理。
