# 访客网站与所有者工作台

## 在网页上使用

| 使用者 | 从哪里开始 | 可以做什么 |
| --- | --- | --- |
| 访客 | 首页 → 注册 → 申请套餐 | 登录查看审批状态、到期时间、用量和自己的订阅 |
| 访客 | 首页 → 给管理员留言 | 无需注册即可提问。同一浏览器可查看匿名回复，登录后提交的问题可跨设备查看 |
| 所有者 | 本机节点运维 → 打开线上访客后台 | 经受限 SSH 通道进入日本站点，审批公网申请、回复留言和签发联网可用的通行证 |
| 所有者 | 首页 → 处理申请 | 勾选申请，选择批准或停用。批准后访客刷新账户页即可领取 |
| 所有者 | 节点运维 → 直接签发 | 选择套餐、生成链接，复制详情中的私有订阅给收件人 |
| 所有者 | 节点运维 → 管理套餐 | 编辑名称、有效小时、十进制 GB 和人民币展示价。已提交申请保留原条款 |
| 所有者 | 节点运维 → 日本个人节点 | 分别检查订阅下载、核心健康和管理通道。配置了私有适配器的电脑还可提交维护操作 |

默认套餐从批准时开始计时，72 小时内可使用上下行合计 **10,000,000,000 字节**。套餐价格只用于展示，首版人工审批，账户内通知。一名注册用户可提交一份申请，所有者可以直接签发多张独立通行证。临时链接是持有者凭证，收到的人可以转发，多设备共用同一份额度。签发给两个人时创建两张，即可分别撤销。

**本机工作台在 `http://127.0.0.1:18766/owner/`。** 配置公网实例后，工作台第一栏列出可分享的访客网址。朋友只需要用浏览器打开该 HTTPS 地址。日本服务独立于所有者的电脑运行。以前在 Windows 上生成的本机测试通行证仍只在本机有效；给别人使用应在“线上访客后台”申请或签发。

## 流量和断开如何执行

节点运维和通行证详情共用管理后台。检查订阅、日本服务器或本机访客入口时，对应按钮下方会显示等待进度、结果、检查时间及耗时。可从详情页顶部的“节点运维”返回。

按订阅 URL 导入 Clash 后，真实访客节点的名称显示剩余流量、剩余时长和北京时间的到期日期。余额是刷新订阅时的快照。服务仍逐次计费和检查期限。Clash Verge Rev 的订阅卡片还能通过响应头读取精确的上下行字节数、额度和到期时间。工作台向支持的客户端建议每小时更新一次，也可手动刷新。[Clash Verge Rev 订阅响应头说明](https://www.clashverge.dev/guide/url_schemes.html)

访客使用 VLESS over WebSocket。订阅凭证和转发凭证分开签名。每次建立 WebSocket 都要验证通行证。网站将字节发给独立的回环 Mihomo 进程，由固定版本核心完成 VLESS 解析。网站到后端使用单独的 TLS 证书，并校验后端身份。生产 HTTPS 配置生成启用 TLS 的客户端条目。个人订阅、个人 UUID 与访客后端相互独立。

上传与下载都在转发前向 SQLite 预扣，所有并行连接共享原子计数。计量涵盖隧道中的协议数据，外层 TLS、WebSocket 和 IP 的开销另计。最后一块数据超过余额时整块拒绝，最多可能剩余 32 KiB 无法用完。若转发中途失败，已预扣的数据仍计入。已到期或已撤销的通行证无法重新认证，每个空闲连接也每秒复查。访客出口限 TCP 80/443，默认拒绝 UDP 和私有网段。

## 运行独立实例

需要 Python 3.12、OpenSSL、匹配系统的维护方 Mihomo v1.19.33 二进制。新建专用的非特权账户与仓库外的私有状态目录。源码启动示例如下。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-portal.txt
.venv/bin/python scripts/guest-portal.py --state /var/lib/relay-guest init
.venv/bin/python scripts/guest-portal.py --state /var/lib/relay-guest serve --core /opt/mihomo/mihomo
```

管理员用户名与随机初始密码保存在私有目录的 `owner-login.txt`。登录后可在 Django 后台修改密码。Windows 使用虚拟环境里的 `Scripts/python.exe`，给 `serve` 加 `--open` 可启动网站并打开浏览器。只运行一个服务实例。完整备份需包含用户数据库、签名密钥和访客 TLS 文件，备份期间停止访客实例，并加密产物。个人节点的备份命令仅负责它自己的目录。内部回环证书有效期一年，更新时在停用的访客实例中成对替换证书和私钥。

## 部署给外部访客之前

用新的状态目录，初始化时指定 `--origin https://guest.example.com`。网站和后端继续监听本机回环。为独立域名配置有效证书。HTTPS 反向代理只转发访客页面、静态资源、`/s/*` 和 WebSocket `/connect`，保留原始 Host，覆盖 `X-Forwarded-Proto` 为 `https`。公网拒绝 `/admin*` 和 `/owner*`。私有管理入口经独立受保护的 HTTPS/SSH 通道访问。不要给来访者网站配置所有者 SSH 密钥或 Docker socket。

公网实例使用独立 Linux 用户、SQLite 数据库和 systemd 服务。边缘代理覆盖 `X-Relay-Peer` 为真实请求来源；单工作进程按来源和总体限制注册、登录、留言、申请与 WebSocket 握手频率。地址仅用于内存中的带密钥计数。留言和回复仅对原访客及管理员可见。Uvicorn 并发上限为 100，systemd 限制内存 196 MiB、CPU 50%。主机按访客 UID 拦截回环、内网、元数据和本机公网地址的新连出连接，单独允许后端 TLS 和本地 DNS。请定期检查数据库和磁盘容量。访问日志不记录带令牌的路径。

生产部署所用的文件包括[服务单元](../templates/guest/relay-guest.service)、[出口策略](../templates/guest/guest-egress.sh)、[边缘代理套接字](../templates/guest/relay-guest-edge.socket)和[Caddy 路由示例](../templates/guest/Caddyfile.example)。详细部署和恢复顺序见[公网访客入口运维](guest-public.md)。

## 个人节点维护

订阅在线检查会下载并校验配置。读取服务器状态另开短时 SSH/LISH 会话，检查预先固定的网关及来宾主机密钥、容器标签、健康和运行镜像。操作结束即关闭会话。网页关闭后，服务器上的 Docker 容器继续工作。

私有工作台的“重启日本代理核心”只排队重启已确认健康且镜像匹配的核心容器，会中断其现有会话。稍后重新读取健康和启动时间确认结果。“应用已验证更新”在镜像已匹配时直接报告当前版本。若有新版本，节点还必须预置管理员审核的 `relay-apply-approved.service`，包含备份、验收、超时回滚；缺少该单元会拒绝更新。代码发布本身不会改动生产版本。主机级重启可使用云厂商控制台。

维护适配器只在本机实例由通过身份验证的超级管理员使用。可选的私有 `settings.json` 字段有 `owner_console_url`、`owner_subscription_file`、`owner_proxy_port`，以及包含 `gateway`、`instance`、`user`、`identity`、`known_hosts`、`guest_fingerprint` 的 `maintenance`。它通过已配置的本机代理访问 LISH，或可从云控制台独立恢复。LISH 须已有可用的来宾管理会话。若管理通道断开，提交结果不明时先读状态再重试。

## 验收

```bash
.venv/bin/python scripts/test-guest-portal.py --core /opt/mihomo/mihomo
```

测试临时创建证书、两个隔离的 Mihomo 和本地 HTTP 目标，覆盖注册、审批、幂等签发、预扣、并发、到期和撤销。用缩小的额度加速触发截止。

11 月 1 日的公网验收使用真实 HTTPS 注册、申请、留言、私有后台回复和批准。隔离的 Mihomo 经已知可达的日本入口访问公网访客节点，成功转发 HTTPS 并计量上下行。停用后，旧链接返回 404，缓存的转发凭据被拒绝。日本和新加坡的独立探针访问注册页返回 200。此次中国大陆探针失败，维护电脑当前网络直连超时。手机宽度浏览器通过界面验收，未在真实手机蜂窝网络上确认可达。个人节点三份订阅内容校验一致。

[Django 管理后台](https://docs.djangoproject.com/en/5.2/ref/contrib/admin/) · [Mihomo 管理界面配置](https://wiki.metacubex.one/en/config/general/) · [个人节点维护](server-setup.md)
