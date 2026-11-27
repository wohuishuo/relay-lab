# 访客访问

需要临时分享时，可以单独运行访客网站。每张通行证有自己的订阅、到期时间和流量余额。个人节点的凭据保存在原节点。

## 发放和撤销

访客在网站注册并申请套餐，管理员批准后，访客从账户页取得订阅。管理员也可以直接签发。默认套餐自批准时起有效 72 小时，上下行合计 10 GB（十进制）。同一张通行证在多台设备上共用余额；需要单独撤销时，为每人各签发一张。

访客通过 WebSocket 连接网关。网关核验通行证，把流量转给独立的 Mihomo，转发前在 SQLite 中扣除字节数。到期、撤销或额度不足时停止转发。客户端显示的剩余额度以最近一次订阅刷新为准。访客出口限 TCP 80/443。

## 本机运行

准备 Python 3.12、OpenSSL 和与平台匹配的 Mihomo v1.19.33。以非特权用户运行，选择该用户可写的私有状态目录。以下命令在源码根目录执行。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-portal.txt
guest_state="$HOME/.local/state/relay-guest"
.venv/bin/python scripts/guest-portal.py --state "$guest_state" init
.venv/bin/python scripts/guest-portal.py --state "$guest_state" serve --core /opt/mihomo/mihomo
```

用浏览器访问 `http://127.0.0.1:18766/owner/`，初始管理员登录信息在状态目录的 `owner-login.txt`。本机签发的回环地址仅供本机验证。对外服务时，先按[公网部署说明](guest-public.md)设置 HTTPS 域名和独立实例。

## 备份与检查

停用实例后，将数据库、配置、签名密钥和内部 TLS 文件一起加密备份。个人节点的备份命令只处理个人状态目录。修改后台或出口策略后，可用 `.venv/bin/python scripts/test-guest-portal.py --core /opt/mihomo/mihomo` 检查注册、审批、流量计量、到期及撤销。
