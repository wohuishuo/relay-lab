# 10 · DNS API、ACME 与证书加载

**目标：** 能独立解释申请、续期、加载和验证。**前置：** 09。

## 身份材料各司其职

| 材料 | 谁使用 | 保管位置 |
| --- | --- | --- |
| DNS API token | lego 修改验证区 TXT | 仓库外私有凭据文件 |
| ACME 账户密钥 | 证书颁发机构账户 | 私有状态与加密备份 |
| 证书私钥 | TLS 服务端 | 受限挂载，不给客户端 |
| 证书链 | 服务端提供，客户端验证 | 可公开但不应泄露部署身份 |
| 协议密码 / UUID | 代理双方认证 | 私有客户端配置与服务端状态 |

联系邮箱用于 ACME 账户联系，不是域名，也不必与购买 VPS 的邮箱一致。REALITY 密钥是另一套材料，不能用 DNS token 或 TLS 私钥替代。

## DNS-01 流程

```text
lego → ACME 下单 → 得到挑战
     → Cloudflare API 写入 _acme-challenge TXT
     → 等待权威 DNS 可见 → ACME 验证 → 下载证书 → 清理挑战
```

DNS-01 不需要为挑战开放入站 80。第一次先用 staging，成功后再用正式环境；staging 证书不能作为公网信任证书部署。参考 [Let's Encrypt 挑战说明](https://letsencrypt.org/docs/challenge-types/)。

Cloudflare token 使用指定区域的 Zone:Read 与 DNS:Edit，或拆分读取/写入 token，避免全局 API key。也可把验证域委派到独立区域以缩小权限。变量名依 [lego Cloudflare provider](https://go-acme.github.io/lego/dns/cloudflare/)；本项目固定 lego 5.4.1，其命令为 `run --renew-days 30`，不是旧版本的 `renew --days`。

## 续期不等于加载

新证书落盘后，进程可能仍持有旧证书。`jp/renewal.py` 比较证书内容；变化时保留旧文件，停止核心，校验域名/链/私钥匹配，替换并启动。失败时尝试恢复有效旧证书，同时返回失败。此方案有短暂停机，不能承诺无损热更新。

如果启用了订阅 HTTPS，`scripts/renew.py` 还会刷新订阅容器的证书副本。核心与订阅两处都必须验证。安装向导配置每天两次检查，提前 30 天续期；只在证书变化时重启。

## 练习与检查点

本地测试生成隔离 CA：正确链和域名成功；错误 CA、错误域名、错误私钥失败。运行 `scripts/run-tests.py` 可验证证书函数；全协议实验验证客户端实际拒绝不可信证书。

检查点：证书文件日期更新但客户端仍看到旧证书，应检查加载路径和容器挂载，而非关闭验证。证书到期告警应监控**实际服务呈现的证书**，同时查看磁盘证书，区分续期失败与加载失败。继续：[部署边界](11-deployment.md)。
