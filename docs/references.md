# 官方资料与证据地图

核对日期：2026-09-20 UTC。滚动文档解释概念；具体字段以固定版本源码和本地运行结果为准。以下都是维护者、标准组织或官方项目资料。

| 主题 | 资料 | 本课程用途 |
| --- | --- | --- |
| 核心版本 | [Mihomo v1.19.31](https://github.com/MetaCubeX/mihomo/tree/v1.19.31) | 配置与许可边界 |
| 详细字段 | [固定源码索引](sources.md) | 每入口配置来源 |
| TCP | [RFC 5681](https://www.rfc-editor.org/rfc/rfc5681.html) | 拥塞、窗口与确认 |
| TLS | [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446.html) | 握手与 0-RTT 限制 |
| QUIC | [RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html)、[RFC 9002](https://www.rfc-editor.org/rfc/rfc9002.html) | 流、丢包恢复和拥塞 |
| REALITY | [XTLS/REALITY](https://github.com/XTLS/REALITY) | 机制与握手目标 |
| Hysteria2 | [协议规范](https://v2.hysteria.network/docs/developers/Protocol/) | 认证与带宽协商 |
| TUIC | [协议规范](https://github.com/tuic-protocol/tuic/blob/master/SPEC.md) | v5 与数据通路 |
| AnyTLS | [协议文档](https://github.com/anytls/anytls-go/blob/main/docs/protocol.md) | 会话与填充 |
| Trojan | [协议文档](https://trojan-gfw.github.io/trojan/protocol) | TLS 内代理请求 |
| XHTTP | [Project X 文档](https://xtls.github.io/config/transports/xhttp.html) | 模式概念，不作为 Mihomo 字段表 |
| SS | [AEAD](https://shadowsocks.org/doc/aead.html)、[入站](https://wiki.metacubex.one/config/inbound/listeners/ss/) | 普通配置与可选插件 |
| SS 代际与算法 | [SIP022](https://shadowsocks.org/doc/sip022.html)、[RFC 8439](https://www.rfc-editor.org/rfc/rfc8439.html)、[H.265](https://www.itu.int/rec/T-REC-H.265) | SS 2022、ChaCha 与名称辨析 |
| 校园接入专题 | [Cisco 双向限速](https://www.cisco.com/c/en/us/support/docs/wireless/5500-series-wireless-controllers/113682-bdr-limit-guide-00.html)、[整形与监管](https://www.cisco.com/c/en/us/td/docs/routers/ios-xe/quality-of-service/quality-of-service/m_qos-plcshp-oview-0.html) | 设备能力示例，不代表当前校园配置 |
| DNS | [Cloudflare proxy status](https://developers.cloudflare.com/dns/proxy-status/)、[Mihomo DNS](https://wiki.metacubex.one/config/dns/) | 解析和接管边界 |
| DNS API | [lego Cloudflare](https://go-acme.github.io/lego/dns/cloudflare/) | token 权限与变量名 |
| ACME | [Let's Encrypt challenges](https://letsencrypt.org/docs/challenge-types/) | DNS-01 与 staging |
| 容器防火墙 | [Docker](https://docs.docker.com/engine/network/packet-filtering-firewalls/) | NAT/转发与 UFW |
| 观测 | [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)、[conntrack](https://docs.kernel.org/networking/nf_conntrack-sysctl.html) | 压力和连接状态 |
| 测量 | [curl](https://curl.se/docs/manpage.html)、[iperf3](https://software.es.net/iperf/invoking.html) | 指标语义 |
| 可靠性 | [Google SRE SLO](https://sre.google/workbook/implementing-slos/)、[错误预算](https://sre.google/workbook/error-budget-policy/) | 服务目标与决策 |

生产路径推断与容量规划属于本项目的分析，不是上游对某条网络的诊断。实验结果以[证据页](evidence.md)中的 JSON 为准。
