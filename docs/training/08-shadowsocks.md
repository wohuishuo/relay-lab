# 08 · Shadowsocks：需要插件吗，为什么 TCP 不通

**目标：** 能分清加密方法、协议代际、插件，以及认证失败与基础网络失败。**前置：** 03。

## 本配置不需要插件

本仓库选择普通 AEAD `chacha20-ietf-poly1305`，TCP 和 UDP 均启用。双方匹配加密方法、密码、地址和端口即可；没有额外插件要求。ShadowTLS、obfs 等属于额外组合，只有双方明确使用时才配置。参考 [AEAD 规范](https://shadowsocks.org/doc/aead.html) 与 [Mihomo 入站文档](https://wiki.metacubex.one/config/inbound/listeners/ss/)。

SS 2022 是另一组方法和密钥约束，例如指定长度的 base64 密钥；不能把普通密码原样搬过去。本项目没有声称测试过 SS 2022。普通 SS 的安全层也不是 X.509 TLS：没有证书选项，并不等同于 TLS 入口关闭了验证。

## 先读完整名称：H.265 不是 SS 加密方法

`H.265 / HEVC` 是视频编码标准，负责压缩视频，与 Shadowsocks 加密无关。这里提到的名称可能是 `aes-256-gcm` 或其他选项，但在没有完整原文前不能作此认定。`Hysteria2 / HY2` 也不是 SS 的 cipher，它是另一种代理协议。参见 [ITU H.265](https://www.itu.int/rec/T-REC-H.265)。

不要只说“ChaCha”或“AES”：`chacha20-ietf` 与 `chacha20-ietf-poly1305` 不能互换；`aes-256-cfb` 与 `aes-256-gcm` 也不是同一安全构造。

## 常见名称到底有什么区别

| 完整方法名 | 代际 / 构造 | 密钥与性能含义 | 本项目验收范围 |
| --- | --- | --- | --- |
| `chacha20-ietf-poly1305` | 传统 SS AEAD；ChaCha20 加密 + Poly1305 认证 | 256 位密钥；纯软件平台通常有优势，仍需看实现 | 当前选用；已测正确与错误认证、TCP/UDP |
| `aes-128-gcm` | 传统 SS AEAD；AES + GCM 认证 | 128 位密钥；AES 硬件指令可加速 | 仅作为客户端错误方法负例，未做匹配双方的完整验收 |
| `aes-256-gcm` | 传统 SS AEAD；AES + GCM 认证 | 256 位密钥；不意味着速度或“抗限速”能力更高 | 未单独验收 |
| `2022-blake3-aes-128-gcm` | SS 2022 | 16 字节随机预共享密钥，base64 编码 | 未验收；不能直接替换配置 |
| `2022-blake3-aes-256-gcm` | SS 2022 | 32 字节随机预共享密钥，base64 编码 | 未验收 |
| `2022-blake3-chacha20-poly1305` | SS 2022 的可选方法 | 需核对双方实现支持及相应密钥要求 | 未验收 |
| `aes-*-cfb`、不带 Poly1305 的旧 ChaCha 方法 | 老式 SS stream 构造 | 缺少上述 AEAD 的完整性/认证保护 | 不用于新部署 |

表中的位数是密钥大小，不是带宽；ChaCha20 的 20 是轮数，不是 20 位密钥。Poly1305 的名称也不是“1305 位加密”。算法执行速度与 CPU 的 AES 指令、软件库和实现有关；不能断言“手机一定 ChaCha 快”或“服务器一定 AES 快”。依据：[SS AEAD](https://shadowsocks.org/doc/aead.html)、[RFC 8439](https://www.rfc-editor.org/rfc/rfc8439.html)。旧 SS stream 方法的退役说明见[官方配置文档](https://shadowsocks.org/doc/configs.html)；这不代表使用 ChaCha20 的现代 AEAD 也被弃用。

## SS 2022 不只是把算法换个名字

SS 2022 调整了报文格式、会话处理与重放保护；BLAKE3 用于子密钥派生，不是额外一层网络传输。它要求直接提供固定长度的随机 PSK，不能把随意输入的登录密码当作同样的配置。base64 是编码，不是加密；16/32 是解码后的字节数，而非字符串字符数。

因此 `aes-256-gcm` 与 `2022-blake3-aes-256-gcm` 虽然都包含 AES-256-GCM，线上格式仍不兼容。某些多用户实现另有 identity key / user key 结构，需要按具体核心版本核对，不能仅靠拼接字符串猜测。2022 规范也明确不提供前向保密；“更新”不等于具备 TLS 全新密钥交换的全部属性。参见 [SIP022](https://shadowsocks.org/doc/sip022.html)。

## 换加密方法能修复校园网下载慢吗

只有先证明加解密是瓶颈，换方法才是有针对性的性能试验。如果 CPU 已满、其他资源充足，可在隔离环境固定载荷和核心版本，对双方匹配的方法分别测试吞吐、CPU 和能耗。**本轮没有执行 AES 与 ChaCha 的匹配性能对照，也没有改现有服务器。**

如果瓶颈是校园出口对外层 TCP 的限速，换 AES/ChaCha 不会把外层 TCP 变成 QUIC。TCP 三次握手都没完成时，cipher 尚未参与代理数据解密，优先查传输路径。SS、SSR、ShadowTLS 插件与 HY2 应分别看待：协议家族、额外承载和加密方法是不同维度。

检查点：服务端 `aes-256-gcm`、客户端 `2022-blake3-aes-256-gcm`、密码文字完全相同，能否连接？不能因此期待兼容；协议代际和密钥格式均不同。

## 根据连接阶段决策

```text
TCP SYN 发出
 ├─ 服务器没看到：检查目标地址、上游路径、云防火墙
 ├─ 服务器回 SYN/ACK，但客户端不完成 ACK：检查回程/客户端路径
 └─ 三次握手完成
     ├─ 加密/认证不匹配：核对 method/password、客户端实际配置
     └─ 请求已解码：检查目标解析、出口规则和目标服务
```

已有排障记录曾出现 SYN/ACK 重传而没有完成握手。这个证据说明失败在认证前，**不能证明缺插件，也不能单凭它断定某个网络运营方的具体策略**。本轮遵守生产冻结，没有重新抓包或改变端口，所以生产根因仍未确认。

## 已完成的本地实验

同一固定版本下，SS 正确密码的 TCP/UDP 转发成功，错误密码与错误加密方法均被拒绝；重启以及 1.19.30 → 1.19.31 切换后恢复。见[本地证据](../evidence.md)与 `reports/ss-local.json`。这反驳“这份配置天生必须装插件”，但不反驳真实链路的过滤或丢失。

```bash
python3 scripts/manage.py local-test --state /tmp/relay-ss-new --protocols ss
```

未来得到维护窗口后可比较：同客户端换接入网、同协议临时测试端口、同路径不同协议。一次只变一项，临时端口需单独授权并限制来源；当前项目没有执行这些服务器操作。

检查点：UDP DNS 转发成功能证明 SS TCP 可用吗？不能；它们是两个独立的传输路径。继续：[DNS](09-dns.md)。
