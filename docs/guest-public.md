# 部署公网访客网站

1. 新建非特权用户 `relay-guest`。将程序、依赖和 Mihomo 安装到服务用户只读的目录，将 `/var/lib/relay-guest` 设为该用户独占可写。现成的路径和资源限制见 [systemd 单元](../templates/guest/relay-guest.service)。
2. 使用访客服务的 Python 和账号运行 `scripts/guest-portal.py --state /var/lib/relay-guest init --origin https://guest.example.com:2087`，替换成有有效证书的实际域名和端口。已有实例先备份，再运行 Django 迁移和静态文件收集。
3. 网站与访客核心监听回环地址。核对宿主机的本地 DNS、Caddy 用户和挂载路径，安装[出口规则](../templates/guest/guest-egress.sh)、[边缘套接字](../templates/guest/relay-guest-edge.socket)及对应服务单元。确认网站能通过套接字接受 Caddy 的连接。
4. 备份现有 Caddy 配置，将[访客路由](../templates/guest/Caddyfile.example)放在兜底 404 规则之前，替换 Host，验证后重载。公开访客页面、订阅和 WebSocket，管理路径仅通过受限的私有通道访问。
5. 从外部验证注册、批准、转发与撤销，确认公网访问管理路径返回 404。若与个人订阅共用 HTTPS 端口，同时复查原订阅。

## 管理通道

工作台支持将远端后台转发到管理设备的回环地址。私有设置 `public_guest` 包含 `origin`、`ssh_host`、`identity`、`known_hosts`。专用 SSH 身份只允许转发到远端 `127.0.0.1:18766`，关闭 shell、PTY、X11 和代理转发。建立隧道后，在管理设备访问 `http://localhost:18769/owner/`。

回退网站路由时，恢复 Caddy 配置并重载。升级后核对数据库、内部证书和出站限制。网站数据与节点备份分开保存。[访客访问](guest-portal.md)
