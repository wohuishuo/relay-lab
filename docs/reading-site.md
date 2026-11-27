# 离线阅读文档

在源码根目录运行以下命令，构建可搜索的静态手册。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-docs.txt
.venv/bin/python scripts/build-docs.py
```

在浏览器打开 `site/index.html`。Windows 的虚拟环境解释器为 `.venv/Scripts/python.exe`。图、样式、搜索和测试图表都随站点生成；外部上游资料需要联网。
