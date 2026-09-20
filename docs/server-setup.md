# 上传后部署：Ubuntu 24.04 LTS / amd64

本说明不表示已执行远程操作。你需要：日本 VPS、域名及支持 API 的 DNS 托管、管理来源 IP/CIDR、实际客户端版本。域名记录应指向 VPS，直连模式不要启用 CDN 代理。先使用两个默认入口。

## 1. 保留管理通道，再做网络变更

1. 在 Linode 控制台实际验证 Lish/控制台登录；保留当前 SSH 会话。
2. 配置 SSH 公钥登录，并用第二个新会话成功登录，再考虑关闭密码登录。SSH 私钥只在本机。
3. 云防火墙采用默认拒绝入站：TCP 22 只允许管理来源，TCP 443/UDP 443 为代理入口；可选协议按端口表逐个放行。对 IPv6 也设置拒绝策略，不发布 AAAA 时不要误开放 IPv6。
4. 主机防火墙变更先导出规则，使用 `systemd-run --on-active=3m` 安排恢复脚本，再应用候选规则。确认新 SSH 会话和必要服务可达后取消恢复任务。不要在尚未测试控制台恢复时批量替换 SSH/防火墙配置。

Docker bridge 发布流量走转发/NAT，不能依赖 UFW 的普通 INPUT 规则挡住容器端口。保留 Docker 自动生成的规则，额外规则在实际 backend 对应的用户过滤链实施。默认 iptables backend 使用 DOCKER-USER；若改为 nftables backend 必须使用相应 nftables 转发规则，不能混用本说明。生产仅绑定 IPv4 `0.0.0.0`，并不因此假定宿主 IPv6 已被保护。

项目不自动修改 SSH 或防火墙，避免把未提供的管理来源猜成正确值。云防火墙必须同时关联正确实例/接口。DNS、时间同步、镜像下载、ACME 以及实际代理转发需要出站；不要把出站仅限 443 后误以为任意代理目标仍能工作。保留 ICMP/PMTU 所需流量。

## 2. 安装基础环境

上传并解压源码至 `/opt/relay-lab`，工作目录切到这里。使用 Docker 官方 Ubuntu 仓库安装 Engine 和 Compose plugin；按官方安装文档操作，记录安装后的实际版本。不要运行不明一键脚本。

```bash
sudo apt-get update
sudo apt-get install -y python3 openssl ca-certificates curl
sudo python3 scripts/manage.py doctor
sudo python3 scripts/manage.py pull
sudo python3 scripts/manage.py install-tools --directory /opt/relay-lab-tools
sudo install -d -m 700 /var/lib/relay-lab
```

本地测试基线 Engine 29.5.3 / Compose 5.1.4；Ubuntu 包版本必须在目标机重新记录，不能声称相同 Windows Desktop 测试覆盖 Linux 主机防火墙。脚本依赖 Compose 的 `up --wait`。

## 3. 准备非敏感设置

复制 `templates/settings.example.json` 到 `/var/lib/relay-lab/settings.json`，修改服务器地址、证书域名、REALITY SNI 与握手目标。`example.org` 是占位符，不能直接部署。

REALITY 目标需从 VPS 实测 TLS 1.3、预期 SNI/证书、可达性和连接稳定性；不能仅从本机通就认定 VPS 也通。初始只填 `reality`、`hy2`；扩展协议 ID 见端口表。

```bash
sudo python3 scripts/manage.py prepare --state /var/lib/relay-lab --settings /var/lib/relay-lab/settings.json
```

记下返回的 release ID。UUID、协议密码和 REALITY 密钥由系统随机源与 Mihomo 官方工具生成，不输出到终端。每次 prepare 创建新目录，不覆盖已有配置。

## 4. 申请证书

使用 lego 对应 DNS provider 文档中的环境变量名，在 `/var/lib/relay-lab/dns-credentials.json` 填写 JSON，例如你的 provider 所需的 API token。模板中的变量名不是实际 provider 名称；不要照抄。文件权限 600，父目录 700。为 `_acme-challenge` 所需区域配置最小授权，最好使用独立验证区域。

先测试 ACME staging，再正式申请。staging 证书不会安装进代理核心。

```bash
sudo python3 scripts/manage.py acme --state /var/lib/relay-lab --domain YOUR_DOMAIN --email YOUR_EMAIL --provider YOUR_PROVIDER --credentials /var/lib/relay-lab/dns-credentials.json --lego /opt/relay-lab-tools/lego --staging
sudo python3 scripts/manage.py acme --state /var/lib/relay-lab --domain YOUR_DOMAIN --email YOUR_EMAIL --provider YOUR_PROVIDER --credentials /var/lib/relay-lab/dns-credentials.json --lego /opt/relay-lab-tools/lego
```

也可导入已有公信证书：`install-cert --state ... --certificate /path/fullchain.pem --key /path/key.pem --domain YOUR_DOMAIN`。必须包含正确域名、匹配私钥和完整证书链。客户端始终验证 TLS；不得通过 `skip-cert-verify` 绕过部署错误。

填写 `templates/jp-proxy-renew.service` 的域名、邮箱、provider 和路径，然后安装 service/timer 至 `/etc/systemd/system`，执行 `systemctl daemon-reload` 和 `systemctl enable --now jp-proxy-renew.timer`。首次手工启动 service 并检查退出结果。续期每日检查两次，提前 30 天续；仅证书改变时停止核心、校验、替换并重启，存在短暂断线。失败恢复仍有效的旧证书，失败状态不伪装成功；systemd 失败和证书到期需要你监控。

## 5. 校验与启动

```bash
sudo python3 scripts/manage.py validate --state /var/lib/relay-lab --release RELEASE_ID
sudo python3 scripts/manage.py deploy --state /var/lib/relay-lab --release RELEASE_ID
sudo python3 scripts/manage.py status --state /var/lib/relay-lab
```

`deploy` 确认配置、进程和每个预期 TCP/UDP 监听端口，输出明确要求真实客户端验收。部署失败停止容器，返回非零退出码；旧 current 状态不会被覆盖。若旧版本因失败升级已停，按“回滚”说明恢复。启动健康检查不替代协议认证与转发测试。

## 6. 导出与真实验收

```bash
sudo python3 scripts/manage.py export-client --state /var/lib/relay-lab --release RELEASE_ID --protocol reality --output /var/lib/relay-lab-export/reality.yaml
sudo python3 scripts/manage.py export-client --state /var/lib/relay-lab --release RELEASE_ID --protocol hy2 --output /var/lib/relay-lab-export/hy2.yaml
```

通过已有安全文件传输通道下载，导入内置兼容 Mihomo 核心的客户端。导出是单入口完整配置，默认本机 127.0.0.1:17890，严格 MATCH 到该节点，无直连回退。私有 HTTPS 订阅可按 [订阅教程](training/12-subscriptions.md) 单独启用。不要把文件内容截图或贴入公共日志。

逐项完成 [真实服务器验收表](acceptance.md)，包括每个启用入口的 TCP、UDP、错误凭据、证书验证、出口 IP、重启、更新回滚。记录设备应用版本与核心版本。未测的客户端/传输组合不能标为兼容。

## 7. 更新、失败恢复、回滚

更新锁文件后先在本机跑全部协议测试，保留旧镜像。用旧 release 的秘密准备新版本：

```bash
sudo python3 scripts/manage.py prepare --state /var/lib/relay-lab --settings /var/lib/relay-lab/settings.json --reuse-secrets-from OLD_RELEASE_ID
sudo python3 scripts/manage.py deploy --state /var/lib/relay-lab --release NEW_RELEASE_ID
sudo python3 scripts/manage.py rollback --state /var/lib/relay-lab
```

`rollback` 恢复上一次成功版本。**失败升级时 active.current 仍为 OLD_RELEASE_ID，直接再次 deploy OLD_RELEASE_ID 恢复；不要误用 rollback 跳到更早版本。** 回滚镜像和配置绑定，证书保持当前有效版本。不要清理旧镜像，直到新版本和恢复路径都确认成功。

若因凭据泄露而轮换，必须将旧 release ID 加入 `/var/lib/relay-lab/revoked-releases.json` 数组；已撤销版本的 deploy/rollback 均拒绝。多个 release 复用同一秘密时，一并撤销。证书和凭据撤销不能靠恢复备份“撤回”。

## 8. 加密备份与恢复

在本机用已验证的 `age-keygen -o identity.txt` 生成备份身份，再用 `age-keygen -y identity.txt` 导出公钥。服务器只放公钥 `recipient.txt`。解密私钥单独离线保存，不进服务器和备份包。

```bash
sudo python3 scripts/manage.py backup --state /var/lib/relay-lab --recipient-file /root/recipient.txt --output /root/jp-proxy-backup.age --age /opt/relay-lab-tools/age
sudo python3 scripts/manage.py restore --input /root/jp-proxy-backup.age --identity /path/offline-identity.txt --output /var/lib/relay-lab-restored --age /opt/relay-lab-tools/age
```

下载加密包并核对输出的 SHA256，定期在隔离目录解密验证。备份覆盖 release、证书、ACME 账户与当前版本，**不包含 DNS token、SSH 私钥、解密私钥**；DNS token 需另行安全恢复。恢复目录必须全新，拒绝路径穿越、链接、特殊文件；恢复后还要校验、部署及连接验收。管理命令对同一状态目录互斥，避免与 prepare/renew/deploy 同时修改文件；不要绕过脚本手工改动正在备份的状态。

## 9. 容量与流量

```bash
sudo bash scripts/check-host.sh
sudo python3 scripts/manage.py status --state /var/lib/relay-lab
sudo openssl x509 -in /var/lib/relay-lab/certs/live/server.crt -noout -dates
```

核心限制 512 MiB、1 CPU、128 进程；这是初始预算，不是吞吐保证。查看 OOM、连接并发和 UDP 丢包后再调整。日志 10 MiB × 3，核心默认为 silent。检查 journal 占用、Docker 镜像容量、磁盘 inode 和加密备份数量；不运行全局 `docker system prune`。接口流量计数会随重启清零，月度额度以 Linode 控制台为准；本地测试未验证实际计费和跨境线路。

## 本地测试清理

本地测试结束自动清理。每个新状态目录使用独立的 Compose 项目名，见 `jp/local.py` 的 `lab_env`。如果使用 `--keep`，先以 `docker compose ls` 找到该实验对应项目并核对挂载路径，再只清理该项目；不要使用全局清理命令。
