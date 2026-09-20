# 09 · DNS：节点地址、目标解析与 Fake-IP

**目标：** 不把三种 DNS 工作混为一谈。**前置：** 01。

## 三个问题

1. **如何找到节点？** 节点域名 A 记录指向 VPS 的 IPv4；AAAA 是 IPv6，只有端到端验证后才添加。
2. **如何找到目标网站？** 可能由应用、本机系统、客户端核心或服务端解析，取决于接管方式和配置。
3. **如何证明域名属于你？** ACME DNS-01 添加 TXT 挑战记录，这是控制操作，不是日常网站解析。

Cloudflare **DNS only** 返回配置的源地址。开启普通橙云代理后，HTTP 流量经过 Cloudflare 的代理体系，解析返回的地址与行为也不同。它不是任意 TCP/UDP 代理的透明转发器；HY2/TUIC 等直连入口不能简单靠橙云工作。参考 [Cloudflare proxy status](https://developers.cloudflare.com/dns/proxy-status/)。

## 为什么需要先解析代理服务器

若“解析节点域名必须经过节点”，但尚不知道节点 IP，就出现启动依赖循环。客户端 DNS 的 bootstrap、proxy-server-nameserver 与目标 nameserver 是不同职责；本仓库最小配置没有替你启用复杂的 DNS 劫持或 Fake-IP。高级 DNS 应单独实验，并固定客户端版本。

Fake-IP 给应用一个虚拟地址，核心记住它与真实域名的映射，再按规则转发。它不是域名真实公网地址。DNS 显示“奇怪 IP”不一定是污染；先确认是否处于 Fake-IP 模式。参考 [Mihomo DNS 配置](https://wiki.metacubex.one/config/dns/)。

## 本机只读练习

Windows 用 `Resolve-DnsName node.example.com`；Linux 用 `getent ahostsv4 node.example.com`。用自己的**测试域名**替换示例，分别记录 A、AAAA 和 TTL。不要把包含内部域名的整份系统 DNS 缓存贴到公开 issue。

随后画出节点首次连接的解析路径。检查点：购买域名、设置 A 记录是否已经申请了 TLS 证书？没有。DNS API token 是否该填到 Clash 的节点密码栏？绝对不是。继续：[证书](10-certificates.md)。
