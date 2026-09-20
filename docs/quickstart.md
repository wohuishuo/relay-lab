# 安装向导：先计划，再部署

适用于**全新 Ubuntu 24.04 amd64**，初始预算 1 vCPU / 1 GB。现有生产主机不要运行本向导，按[维护手册](server-setup.md)管理 release。本次交付未对真实服务器执行安装或更新。

## 1. 准备前提

- 源码经审查后放到 `/opt/relay-lab`，使用固定提交或 release，避免盲目运行远程脚本。
- 按 [Docker 官方 Ubuntu 安装文档](https://docs.docker.com/engine/install/ubuntu/) 安装 Engine 和 Compose plugin；安装 Python 3.12+、OpenSSL、CA 根证书。
- 域名 A 记录直指节点地址，Cloudflare DNS only；不添加尚未验证的 AAAA。
- 云防火墙默认入站拒绝，SSH 限定管理来源；仅放行所选协议的[端口](ports.md)。验证控制台恢复和第二条 SSH 会话。
- 外部 TLS 握手目标必须由未来目标主机验证兼容性。示例域名不能直接使用。

向导不自动购买资源、安装 Docker、修改 SSH 或防火墙，因为这些涉及主机与管理通道的现有状态。“一键”负责准备完成后的串行部署，不代表跳过这些前提。

## 2. 私有设置与 DNS token

```bash
sudo install -d -m 700 /var/lib/relay-lab
sudo install -m 600 templates/settings.example.json /var/lib/relay-lab/settings.json
sudo install -m 600 templates/cloudflare-credentials.example.json /var/lib/relay-lab/dns-credentials.json
```

用本机/服务器安全编辑器修改这两个文件。设置文件包含节点域名、REALITY 目标和协议清单；DNS 凭据文件只供 ACME 使用，不要贴到命令行、聊天或 Git。参考[证书课程](training/10-certificates.md)。

默认启用 `reality,hy2`；若要全部协议，在 settings 的 protocols 数组逐一填入端口表中的 ID，并提前放行必要端口。每个入口都要独立验收。

## 3. 查看计划

```bash
bash install.sh --settings /var/lib/relay-lab/settings.json
```

此步骤不拉镜像、不申请证书、不创建状态文件、不连接服务器。它验证参数，列出将使用的端口与阶段。发现 existing release 会拒绝，避免当成更新工具使用。

## 4. 显式执行

阅读 [Let's Encrypt 服务条款](https://letsencrypt.org/repository/) 后，在未来新主机本地执行：

```bash
sudo bash install.sh --settings /var/lib/relay-lab/settings.json --email owner@example.com --credentials /var/lib/relay-lab/dns-credentials.json --apply --firewall-ready --recovery-ready --accept-acme-tos
```

先下载固定官方镜像和校验过的工具，再 ACME staging、正式证书、生成随机身份、校验与启动、私有客户端导出、启用续期定时器。任一步失败返回非零；不会打印 token、密码或订阅链接。若失败发生在部署之后的定时器设置阶段，核心可能已运行，但整个安装仍判失败；检查状态后使用维护流程，不要强行清空目录重跑。

输出客户端位于 `/var/lib/relay-lab/client.yaml`。通过安全通道传给自己的设备。向导不默认开放订阅端口；需要链接时再按[订阅教程](training/12-subscriptions.md)操作。

## 5. 必须完成的验收

从实际设备验证每个启用协议的正确认证、错误认证、TCP/UDP、TLS、出口、重启恢复和更新回滚。逐项记录应用与核心版本；模板见 [acceptance.md](acceptance.md)。容器健康检查成功不代表全部验收完成。

## 6. 续期与恢复

`relay-lab-renew.timer` 每天检查两次；证书变化才加载。查看 systemd 失败状态，设置证书到期与请求失败告警。需要加密备份时按[维护手册](server-setup.md)生成 age 身份，解密身份离线保存。

已验证：向导无副作用计划、旧部署拒绝、缺少前提拒绝；其使用的配置、证书、容器与备份组件已本地测试。**未验证：在全新 Ubuntu 云主机执行整条向导、真实 DNS API/正式 ACME、主机重启。**
