# 12 · 链接配置、自动切换与网站

**目标：** 清楚自动切换在哪执行，链接里保护什么。**前置：** 01、02。

## 订阅链接实际下载什么

HTTPS 订阅本质上下载客户端配置。你不必手工管理 YAML，但客户端仍然读取配置结构。链接路径中的随机凭据可以直接获得节点身份，必须当成密码；禁止公开转换网站、工单、截图或访问日志记录完整链接。

本项目可选 Caddy 静态订阅服务绑定 2087，TLS 验证开启、管理 API 关闭、未知路径 404、无目录浏览。它没有用户门户、账户管理或支付功能。教程站点只供阅读，不能控制生产核心。

## 三种客户端策略

| 模式 | 行为 | 不保证什么 |
| --- | --- | --- |
| manual | 用户选择 | 不会自动判断故障 |
| fallback | 按顺序选可用节点 | 不按下载吞吐排序 |
| url-test | 用指定 URL 的响应延迟选择 | 延迟最小不等于带宽最大 |

仓库可**离线生成**这三种配置：

```bash
python3 scripts/export-bundle.py --state /var/lib/relay-lab --release RELEASE_ID --mode fallback --output /var/lib/relay-export/fallback.yaml
```

输出只有代理候选，没有 DIRECT 自动回退。规则入口 `Relay` 保留手动选择；自动组每 120 秒检查，url-test 容差 50 ms。导入前核对节点顺序和探测 URL。访问该 URL 会产生少量真实流量；URL 自身故障也可能造成误判。参见 [fallback](https://wiki.metacubex.one/config/proxy-groups/fallback/) 与 [url-test](https://wiki.metacubex.one/config/proxy-groups/url-test/)。

## 切换的现实边界

探测有周期和超时，因此不是瞬时切换。已建立连接通常不会无损迁移到另一个协议；新请求可使用新的候选。单一健康 URL 只覆盖一条路径，不能证明所有网站可用。

同 VPS 的多协议可以缓解某种传输被阻断，但无法应对整机、机房或共享上游故障。跨服务器切换需要客户端同时拥有不同故障域的节点配置，并进行故障演练；不是在订阅端口再加个服务就能获得。

## 订阅发布步骤（仅在自己的维护窗口）

```bash
python3 scripts/subscription.py prepare --state /var/lib/relay-lab --client /var/lib/relay-lab/client.yaml --domain node.example.com --bind 0.0.0.0 --port 2087
python3 scripts/subscription.py deploy --state /var/lib/relay-lab
python3 scripts/subscription.py check --state /var/lib/relay-lab --public
```

先完成域名、证书与云防火墙；URL 保存在私有状态 `subscription/url.txt`，脚本不打印。`publish` 更新文件，`rotate` 撤销旧链接。链接撤销不等于旧节点密码撤销，二者需要分别处理。

检查点：更新订阅里的 fallback 组是否必须重启服务端核心？不必。它是客户端选择策略；本轮没有发布新生产订阅。
