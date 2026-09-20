# 04 · VLESS + RAW + REALITY

**目标：** 区分 VLESS 身份、REALITY 密钥和握手目标。**前置：** 03。

## 三个名字分别负责什么

VLESS 携带代理请求和用户身份；它本身不是替代 TLS 的加密层。RAW 表示直接的 TCP 传输形态，本仓库 Mihomo 客户端字段为 `network: tcp`，不能把其他核心的新字段名直接搬来。REALITY 负责相应的安全握手，Vision 是这里匹配的 flow。

服务端保留 REALITY 私钥，客户端得到公钥、short ID、UUID、SNI。握手目标是服务端用于 REALITY 行为的外部 TLS 目标，不是用户所有代理流量都必须绕经的网站。选取目标需要服务端侧可达性与兼容性验证；本轮没有连接生产服务器进行这种检查。

## 在代码中找到契约

`server_config` 中服务端 `reality-config` 的 `dest/server-names/private-key/short-id`，与客户端 `reality-opts/public-key/short-id` 和 `servername` 对应。UUID 与 `xtls-rprx-vision` 必须匹配。不要把自己证书的域名误当成 REALITY 一定要使用的 SNI。

本地测试使用受控的 `reality.test` 目标，不访问公网伪装目标。错误 UUID、错误 REALITY 公钥分别验证。普通 TLS 入口的“错误 CA”测试不能代替 REALITY 的公钥负例。

## 实验与检查点

```bash
python3 scripts/manage.py local-test --state /tmp/relay-reality-new --protocols reality
```

如果 TCP SYN 都无法完成，换 UUID 没有诊断价值；若 TCP 已建立、REALITY 验证失败，再检查字段与版本。协议可以正常握手却下载很慢，此时继续测持续传输、重传、窗口和路径，而不是盲目换 SNI。

机制参考 [XTLS REALITY](https://github.com/XTLS/REALITY)；本仓库字段以 [Mihomo v1.19.31 配置](https://github.com/MetaCubeX/mihomo/tree/v1.19.31/listener/config) 与实际实验为准。不能把 Xray 的参数表当作 Mihomo 的承诺。继续：[Hysteria2](05-hysteria2.md)。
