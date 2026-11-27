# 安装个人节点

适用于全新 Ubuntu 24.04 amd64 VPS。已有节点请按[更新与回滚](server-setup.md)操作。以下命令在服务器上运行。

## 1. 准备主机与域名

安装 Git、Python 3.12、OpenSSL、CA 证书，以及支持 `docker compose up --wait` 的 Docker Engine 和 Compose 插件。配置域名的 A 记录指向服务器 IPv4，在 Cloudflare 选择「仅 DNS」。准备该区域的 DNS 编辑和区域读取令牌。确认可以从云控制台恢复 SSH 登录。默认入口需要放行 **TCP 443 和 UDP 443**，SSH 仅对管理来源开放。[Docker 安装说明](https://docs.docker.com/engine/install/ubuntu/) · [lego 所需的 DNS 权限](https://go-acme.github.io/lego/dns/cloudflare/)

```bash
sudo git clone https://github.com/wohuishuo/relay-lab.git /opt/relay-lab
cd /opt/relay-lab
sudo install -d -m 700 /var/lib/relay-lab
sudo install -m 600 templates/settings.example.json /var/lib/relay-lab/settings.json
sudo install -m 600 templates/cloudflare-credentials.example.json /var/lib/relay-lab/dns-credentials.json
sudoedit /var/lib/relay-lab/settings.json /var/lib/relay-lab/dns-credentials.json
```

| 设置 | 填写内容 |
| --- | --- |
| `server`、`domain` | 客户端连接地址、申请证书的域名。初次安装可填同一个节点域名 |
| `reality_sni`、`reality_dest` | 从 VPS 可访问的 TLS 1.3 握手目标。分别填与目标证书匹配的域名和 `主机名:端口` |
| `protocols` | 初次保留 `["reality", "hy2"]`。数组顺序也是普通备用配置的优先级 |
| DNS 凭据文件 | 将模板里的占位值换成对应 Cloudflare API token，保留文件权限 600 |

## 2. 预览并安装

```bash
sudo bash install.sh --settings /var/lib/relay-lab/settings.json
```

核对输出中的协议和端口。确认防火墙、控制台和 [Let's Encrypt 服务条款](https://letsencrypt.org/repository/) 后，填入自己的 ACME 联系邮箱并执行。

```bash
read -r -p 'ACME 联系邮箱：' acme_email
sudo bash install.sh --settings /var/lib/relay-lab/settings.json \
  --email "$acme_email" --credentials /var/lib/relay-lab/dns-credentials.json \
  --apply --firewall-ready --recovery-ready --accept-acme-tos
```

安装器校验工具，先用测试环境验证 DNS 授权，再申请正式证书、启动 Mihomo、导出配置并启用续期定时器。若提示已有部署，先查看[当前版本和恢复步骤](server-setup.md)。安装后期出错时，核心可能已经启动。

## 3. 导入并验证

通过私有文件传输获取 `/var/lib/relay-lab/client.yaml`，导入支持 Mihomo 的客户端，在 `Relay` 组分别选择 `reality` 和 `hy2`。通过代理访问 HTTPS，确认出口是自己的 VPS，再检查需要的 UDP 应用。生成配置的本地 HTTP/SOCKS 入口为 `127.0.0.1:17890`。

默认手动选择入口。[开启自动切换](client-selection.md) · [查看测试和故障排查](evidence.md)
