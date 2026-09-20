#!/usr/bin/env python3
"""Build an offline, dependency-light reading site. Never includes private state."""
import html
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'site'
REPO = 'https://github.com/wohuishuo/relay-lab'


def relative(source, target):
    return os.path.relpath(target, source.parent).replace('\\', '/')


def title(path):
    match = re.search(r'^# (.+)$', path.read_text(encoding='utf-8'), re.M)
    return match[1] if match else path.stem


def main():
    pages = sorted((ROOT / 'docs').rglob('*.md')) + [ROOT / p for p in ('README.md', 'SECURITY.md', 'THIRD_PARTY.md', 'ci/README.md')]
    pages = [p for p in pages if 'plans' not in p.parts]
    lessons = sorted((ROOT / 'docs/training').glob('[0-9]*.md'))
    navigation = [ROOT / 'docs/training/README.md'] + lessons + [ROOT / ('docs/' + name + '.md') for name in ('quickstart','evidence','campus-network','ports','server-setup','references','glossary')]
    for p in navigation:
        if not p.exists():
            raise ValueError('Missing navigation source: ' + p.name)
    OUT.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'docs/assets', OUT / 'docs/assets', dirs_exist_ok=True)
    (OUT / 'reports').mkdir(exist_ok=True)
    for p in (ROOT / 'reports').glob('*.json'):
        shutil.copy2(p, OUT / 'reports' / p.name)
    data = {str(i): p.read_text(encoding='utf-8') for i, p in enumerate(navigation)}
    search_json = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    def shell(output, heading, body, source=None):
        css = relative(output, OUT / 'docs/assets/site.css')
        js = relative(output, OUT / 'docs/assets/site.js')
        home = relative(output, OUT / 'index.html')
        links = ['<span class="section">LEARN / 学习路径</span>']
        for i, p in enumerate(navigation):
            if i == 18:
                links.append('<span class="section">BUILD / 工程手册</span>')
            text = title(p)
            href = relative(output, OUT / p.relative_to(ROOT).with_suffix('.html'))
            cls = 'active' if p == source else ''
            links.append(f'<a class="{cls}" data-page="{i}" href="{html.escape(href)}">{html.escape(text)}</a>')
        edit = (f'<a href="{REPO}/blob/main/{source.relative_to(ROOT).as_posix()}">查看源文档 ↗</a>' if source else '<span>独立项目 · 不隶属于协议维护方</span>')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="RelayLab 中文代理工程课程：协议、可重复实验与可靠性"><title>{html.escape(heading)} · RelayLab</title><link rel="stylesheet" href="{css}"></head><body>
<a class="skip" href="#main">跳到正文</a><header><a class="brand" href="{home}"><span class="mark">R</span>RelayLab</a><span class="tagline">代理工程实验室</span><div class="tools"><a href="{REPO}">GitHub ↗</a><button class="icon" id="theme" aria-label="切换深浅主题">◐</button><button class="icon" id="menu" aria-label="打开目录" aria-expanded="false">目录</button></div></header>
<div class="layout"><aside><label for="search">SEARCH THE HANDBOOK</label><input id="search" type="search" placeholder="搜索协议、DNS、性能…"><p class="empty" id="search-status" aria-live="polite"></p><nav aria-label="课程目录">{''.join(links)}</nav></aside><main id="main"><div class="crumb"><a href="{home}">实验室</a><span>/</span><span>{html.escape(heading)}</span></div>{body}<footer><span>RELAYLAB · 2026 / 本地证据，明确边界</span>{edit}</footer></main></div><script type="application/json" id="search-data">{search_json}</script><script src="{js}" defer></script></body></html>''', encoding='utf-8')
    for p in pages:
        output = OUT / p.relative_to(ROOT).with_suffix('.html')
        renderer = markdown.Markdown(extensions=['extra', 'toc'], extension_configs={'toc': {'toc_depth': '2-3'}})
        content = renderer.convert(p.read_text(encoding='utf-8'))
        def rewrite(match):
            attr, url = match.groups()
            parsed = urlsplit(html.unescape(url))
            if parsed.scheme or parsed.netloc or not parsed.path:
                return match[0]
            target = (p.parent / parsed.path).resolve()
            if not target.exists() or ROOT not in target.parents:
                raise ValueError('Broken/unsafe relative link in ' + str(p.relative_to(ROOT)) + ': ' + parsed.path)
            rel = target.relative_to(ROOT)
            if target.suffix == '.md':
                value = relative(output, OUT / rel.with_suffix('.html'))
            elif rel.parts[0] == 'reports' or 'assets' in rel.parts:
                value = relative(output, OUT / rel)
            else:
                value = REPO + '/blob/main/' + rel.as_posix()
            if parsed.fragment:
                value += '#' + parsed.fragment
            return attr + '="' + html.escape(value, quote=True) + '"'
        content = re.sub(r'(href|src)="([^"]+)"', rewrite, content)
        pager = ''
        if p in lessons:
            i = lessons.index(p)
            prev = lessons[i-1] if i else ROOT / 'docs/training/README.md'
            nxt = lessons[i+1] if i+1 < len(lessons) else ROOT / 'docs/evidence.md'
            pager = f'<div class="pager"><a href="{relative(output, OUT / prev.relative_to(ROOT).with_suffix(".html"))}">← {html.escape(title(prev))}</a><a href="{relative(output, OUT / nxt.relative_to(ROOT).with_suffix(".html"))}">{html.escape(title(nxt))} →</a></div>'
        shell(output, title(p), '<article class="article">' + content + pager + '</article>', p)
    results = json.loads((ROOT / 'reports/directional.json').read_text())['results']
    bench_json = json.dumps(results).replace('<', '\\u003c')
    homepage = '''<div class="hero"><img src="docs/assets/banner.svg" alt="让每一次连接，都有据可查。理解协议、设计实验、构建可靠的个人节点。"></div>
<p class="intro">从一次握手开始，走进协议、DNS 与可靠性的内部。用可运行的实验理解现象，用清晰的证据决定下一步。</p>
<div class="actions"><a class="button" href="docs/training/README.html">开始学习 →</a><a class="button secondary" href="docs/quickstart.html">部署一个新节点</a><a class="button secondary" href="docs/evidence.html">查看验证记录</a></div>
<div class="status"><span class="dot"></span>本地实验已完成 · 生产环境保持不变 · 真实线路根因待验证</div>
<div class="stats"><div class="stat"><strong>17</strong><span>从概念到实践的课程</span></div><div class="stat"><strong>9</strong><span>逐项验收的协议入口</span></div><div class="stat"><strong>150</strong><span>双向传输校验样本</span></div></div>
<div class="section-title"><h2>选择你的第一条路径</h2><span>READ → EXPERIMENT → EXPLAIN</span></div><div class="cards">
<a class="card" href="docs/training/01-system.html"><small>01 / UNDERSTAND</small><h3>看懂一次连接</h3><p>应用、核心、协议与订阅，究竟各自负责什么？</p></a>
<a class="card" href="docs/training/13-performance.html"><small>02 / INVESTIGATE</small><h3>解释上下行差异</h3><p>下载 1 Mbps、上传却很快。把猜测变成可证伪的实验。</p></a>
<a class="card" href="docs/training/15-reliability.html"><small>03 / OPERATE</small><h3>让节点持续可靠</h3><p>资源趋势、恢复演练与错误预算，比定时重启更重要。</p></a></div>
<div class="section-title"><h2>数据如何走到目的地</h2><span>四个边界，一次请求</span></div><div class="flow"><div><b>01 客户端</b><small>接管 · 规则 · 选择</small></div><div><b>02 加密通道 →</b><small>TCP / QUIC · 认证</small></div><div><b>03 代理节点 →</b><small>监听 · 检查 · 转发</small></div><div><b>04 目标服务</b><small>应用响应 · 返回数据</small></div></div>
<div class="section-title"><h2>改变一个条件，观察两个方向</h2><span>本地受控实验 · 中位数 Mbps</span></div><section class="chart" aria-label="方向性实验交互图表"><div class="tabs"><button data-scenario="rtt80" aria-pressed="true">额外 80 ms RTT</button><button data-scenario="download-loss" aria-pressed="false">服务端出口丢包</button><button data-scenario="upload-loss" aria-pressed="false">客户端出口丢包</button><button data-scenario="download-cap" aria-pressed="false">下载方向限速</button></div><div id="bars" aria-live="polite"></div><p class="chart-note">每方向 3 次 × 2 MiB；图表按当前场景缩放。随机丢包设定 1%，下载限速设定 2 Mbps。短流与 VM 调度存在波动，不能作为公网协议排名。</p></section>
<div class="notice">实验能证明某种机制可以产生现象，不能仅凭相似曲线认定真实线路的根因。所有原始样本、测量限制和未完成事项都在证据页中。</div>'''
    shell(OUT / 'index.html', '学习与实验', homepage + '<script type="application/json" id="bench-data">' + bench_json + '</script>')
    print(f'Built {len(pages)+1} pages with local assets and validated relative links')


if __name__ == '__main__':
    main()
