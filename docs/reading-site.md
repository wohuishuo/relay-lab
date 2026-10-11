# Local reading website / 本地阅读网站 / Локальный сайт

[English](../README.md) · [简体中文](../README.zh-CN.md) · [Русский](../README.ru.md)

You can read the handbook directly on GitHub. The optional local website adds chapter navigation, search, theme switching, and interactive experimental charts. It also includes all three repository homepages. The detailed handbook and the website navigation are currently in Chinese. This is a static documentation reader, not a node administration panel.

## Linux / macOS

Run from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-docs.txt
.venv/bin/python scripts/build-docs.py
.venv/bin/python -m http.server 8765 --bind 127.0.0.1 --directory site
```

## Windows / PowerShell

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes -r requirements-docs.txt
.venv/Scripts/python.exe scripts/build-docs.py
.venv/Scripts/python.exe -m http.server 8765 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:8765`. The English, Chinese, and Russian homepages are at `/README.html`, `/README.zh-CN.html`, and `/README.ru.html`. Press **Ctrl+C** to stop serving. Keep the server bound to loopback and serve only the generated `site/` directory, never the source root or a private state directory.

## 中文说明

可以直接在 GitHub 阅读，也可以在仓库根目录运行上面的命令，构建带章节导航、搜索、主题切换和实验图表的本地网站。网站包含三种语言的首页；深入课程与网站导航目前为中文。

打开 `http://127.0.0.1:8765`；中文首页位于 `/README.zh-CN.html`。按 **Ctrl+C** 停止服务。只绑定本机回环地址，只提供生成的 `site/` 目录，不要把源码根目录或私有状态目录设为 Web 根目录。这是静态文档阅读器，不是节点管理面板。

## Пояснение на русском

Руководство можно читать на GitHub или собрать локальный сайт командами выше из корня репозитория. Он добавляет навигацию по главам, поиск, смену темы и интерактивные графики. В сайт включены три языковые версии главной страницы; подробное руководство и навигация пока на китайском.

Откройте `http://127.0.0.1:8765`; русская главная страница находится по пути `/README.ru.html`. **Ctrl+C** останавливает сервер. Используйте только loopback-адрес и каталог `site/`; не публикуйте корень исходного кода или приватное состояние. Это статический сайт документации, а не панель управления узлом.
