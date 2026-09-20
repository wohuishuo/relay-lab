# 14 · 做一份可重复的延迟与吞吐报告

**目标：** 能执行小流量、方向明确、保留负例的实验。**前置：** 13。

## 先定义观察点

一次远程测速包含本机 → VPS 和 VPS → 测速目标两段。普通 speedtest App 还可能自动换目标。只有固定端点、版本、载荷、并发与方向后，结果才可比较。Mbps 是十进制兆比特每秒，MB/s 是字节每秒，二者相差约 8 倍，MiB 又使用 1024² 字节。

每组记录：UTC 时间、匿名网络编号、客户端应用/内核、协议、目标编号、方向、有效字节、耗时、成功/失败、重试、资源指标。至少做顺序平衡：A/B/C，然后 C/B/A。不要删掉低速、超时样本，也不要把失败换算成正常 0 Mbps。

## 只在本机复现实验

```bash
docker build -f lab/Dockerfile.netem -t relay-lab-netem:local .
python3 scripts/benchmark-local.py --state /tmp/relay-bench-new --protocols reality hy2 tuic ss --scenarios rtt80 download-loss upload-loss download-cap --mib 2 --repeats 3
```

实验 helper 只对带有本次 Compose 标签的容器网络命名空间使用 NET_ADMIN，不能改宿主网络，不挂载 Docker socket。所有实验容器无公网服务端口。此特殊能力仅供本地 netem；生产核心仍 drop ALL。

载荷上限 16 MiB、每方向最多 5 次，单次有超时边界。目标验证 nonce 或 SHA256，避免下载到错误页面也算成功。`2 MiB × 2 方向 × 3 次 × 4 协议 × 4 场景 = 192 MiB` 为实验有效载荷，不含封装；完全发生在本机虚拟网络。

## 未来客户端小流量测量

选择自己控制或明确允许测速的 HTTPS 静态文件。以下命令只在主动需要时执行；Windows 用 `curl.exe` 避免 PowerShell 别名：

```bash
curl --proxy http://127.0.0.1:17890 --noproxy "" --fail --silent --show-error --max-time 20 --output /dev/null --write-out 'connect=%{time_connect} tls=%{time_appconnect} first=%{time_starttransfer} total=%{time_total} bytes=%{size_download} bytes_per_second=%{speed_download}\n' https://test.example.com/fixed-2MiB.bin
```

Windows 输出丢弃目标换成 `NUL`。不要加 `-k`。代理模式下 `time_connect` 可能只测到本机代理端口，`time_appconnect` 通常对应目标 HTTPS TLS，**不等于外层代理握手**。这些语义来自 [curl 官方手册](https://curl.se/docs/manpage.html)。测代理握手需核心级观测或两端受控抓包，本仓库未声称完成公网握手分解。

## iperf3 能测什么

在另一个获授权的测试主机运行 iperf3，可分别测 `-R` 反向、单流与多流、UDP 丢包/jitter，并用 `-J` 保存 JSON。普通 iperf3 不原生经过 HTTP/SOCKS 代理；它测的是端点之间路径，除非你已正确建立受控隧道/TUN。不要把它的直连结果记为代理性能。

公开 iperf3 服务需限制来源和运行时间；当前项目没有在生产安装或开放它。参数以 [ESnet 文档](https://software.es.net/iperf/invoking.html) 为准。

## 检查点

一张好报告不仅有中位数，还给出样本数、min/max、失败数和限制。若要评估尾延迟/P95/P99，3 个样本显然不足；不要从三点曲线得出 SLA。基线改善后仍需验证认证、TLS、DNS/IPv6 泄漏与业务成功率。
