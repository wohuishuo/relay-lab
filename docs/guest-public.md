# 公网访客入口运维

门户运行在节点上。个人节点的管理员凭据保存在维护电脑。网上的访客用浏览器访问、注册和留言；访问服务的套餐须经审批。

## 部署顺序

1. 核实订阅 HTTPS 证书、可用内存和空间，并保留独立管理通道。保存现有 Caddyfile 的私有副本，记录现有订阅的 SHA-256。
2. 为访客新建非特权系统账户 `relay-guest`。把仓库程序放在只读安装目录，按 `requirements-portal.txt` 校验并安装依赖，准备 v1.19.33 的 Mihomo 二进制。单元示例的目录是 `/opt/relay-guest/{app,libs,mihomo}`，可以使用当前固定摘要容器内的同一维护方二进制。把可写状态目录 `/var/lib/relay-guest` 设为仅访客服务用户可访问。
3. 以访客服务用户身份初始化 HTTPS origin，包含实际端口。新安装执行 `scripts/guest-portal.py --state /var/lib/relay-guest init --origin https://guest.example.com:2087`。已有实例更新时，在私有备份后执行 Django 的 `migrate` 和 `collectstatic`，沿用数据库与签名密钥。
4. 安装 `templates/guest/` 中的 systemd 单元和出口脚本。先核对本机 DNS、Caddy 的运行 UID、宿主机路径、出口规则及已有防火墙。示例使用宿主机 stub resolver 127.0.0.53。确保 Caddy 容器中 /config 对应的宿主机目录内有 guest 子目录，属主为容器 UID，模式 0500。边缘套接字只允许该 UID 连接。启用并启动 relay-guest.service 和 relay-guest-edge.socket，在宿主机本地验证注册页和证书。
5. 将示例 Caddy 路由加入原配置中兜底 404 之前，替换示例 Host。先用运行版本的 Caddy 验证完整配置，设置独立于客户端连接的回滚定时器，再原子替换配置并让以配置文件启动的 Caddy 重读。新站点只共用 HTTPS 端口。个人代理核心不需要重启。验证公网首页/注册、原订阅内容、管理 URL 的 404、访客转发和撤销后再解除回滚定时器。
6. 用户、账单记录、问答文本和签名材料都属于私有数据。备份时可通过 SQLite 在线备份 API 取得快照，将数据库、配置与内部 TLS 文件一并加密，离线保存解密身份并实测还原。回滚前端路由时先恢复原 Caddyfile，再重读并复查原订阅。停用来宾服务不应影响个人代理。修改 UFW 或 Docker 防火墙后，重新验证 UID 出口规则。

## 私有后台

本机工作台的 `public_guest` 配置使用 `origin`、`ssh_host`、`identity`、`known_hosts`，真实值留在私有设置文件。工作台在所有者点击时，以固定的主机密钥和专用 SSH 身份打开回环转发。远端限制该身份为 `AllowTcpForwarding local`、`PermitOpen 127.0.0.1:18766`、`MaxSessions 0`，禁止 shell、PTY、代理转发和 X11。独立密钥、公网后台的独立登录文件均留在本机私有目录。

维护电脑通过自有代理容器抵达同主机 SSH。宿主机规则限该容器源地址、其 bridge 接口和宿主机具体目的地址的 TCP 22。变更前应验证独立控制台、检查 sshd 配置语法和有效账户配置，再重载；禁止将云防火墙 SSH 来源放宽到所有地址。容器地址或 bridge 重建时应重新核对该窄规则。

浏览器使用 `http://localhost:18769/owner/` 进入已建立的隧道；该地址只在维护电脑生效。公网反向代理不转发后台路径。在公网后台签发的通行证会指向公开 HTTPS 域名；Windows 本机测试站点有自己的数据库和通行证。

[返回访客网站](guest-portal.md) · [Caddy 信号与重载](https://caddyserver.com/docs/command-line#signals)
