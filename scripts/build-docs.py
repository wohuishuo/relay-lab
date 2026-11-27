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
from markdown.extensions.toc import slugify_unicode

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'site'
REPO = 'https://github.com/wohuishuo/relay-lab'


def relative(source, target):
    return os.path.relpath(target, source.parent).replace('\\', '/')


def title(path):
    match = re.search(r'^# (.+)$', path.read_text(encoding='utf-8'), re.M)
    return match[1] if match else path.stem


def main():
    pages = sorted((ROOT / 'docs').rglob('*.md')) + [ROOT / p for p in ('README.md', 'README.zh-CN.md', 'README.ru.md', 'SECURITY.md', 'THIRD_PARTY.md', 'ci/README.md')]
    navigation = [ROOT / 'docs' / (name + '.md') for name in (
        'quickstart', 'ports', 'client-selection', 'architecture', 'server-setup',
        'guest-portal', 'guest-public', 'evidence', 'reading-site')]
    navigation += [p for p in pages if p not in navigation]
    OUT.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'docs/assets', OUT / 'docs/assets', dirs_exist_ok=True)
    (OUT / 'reports').mkdir(exist_ok=True)
    for p in (ROOT / 'reports').glob('*.json'):
        shutil.copy2(p, OUT / 'reports' / p.name)
    data = {str(i): p.read_text(encoding='utf-8') for i, p in enumerate(navigation)}
    search_json = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    def shell(output, heading, body, source=None):
        language = {'README.md': 'en', 'README.zh-CN.md': 'zh-CN', 'README.ru.md': 'ru'}.get(source.name if source and source.parent == ROOT else '', 'zh-CN')
        css = relative(output, OUT / 'docs/assets/site.css')
        js = relative(output, OUT / 'docs/assets/site.js')
        home = relative(output, OUT / 'index.html')
        links = []
        for i, p in enumerate(navigation):
            text = title(p)
            href = relative(output, OUT / p.relative_to(ROOT).with_suffix('.html'))
            cls = 'active' if p == source else ''
            links.append(f'<a class="{cls}" data-page="{i}" href="{html.escape(href)}">{html.escape(text)}</a>')
        edit = (f'<a href="{REPO}/blob/main/{source.relative_to(ROOT).as_posix()}">查看源文档 ↗</a>' if source else '<span>个人代理部署</span>')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="个人代理的安装、配置与维护"><title>{html.escape(heading)} · 个人代理部署</title><link rel="stylesheet" href="{css}"></head><body>
<a class="skip" href="#main">跳到正文</a><header><a class="brand" href="{home}">个人代理部署</a><div class="tools"><a href="{REPO}">GitHub ↗</a><button class="icon" id="theme" aria-label="切换深浅主题">◐</button><button class="icon" id="menu" aria-label="打开目录" aria-expanded="false">目录</button></div></header>
<div class="layout"><aside><label for="search">搜索文档</label><input id="search" type="search" placeholder="搜索协议、DNS、性能…"><p class="empty" id="search-status" aria-live="polite"></p><nav aria-label="文档目录">{''.join(links)}</nav></aside><main id="main"><div class="crumb"><a href="{home}">首页</a><span>/</span><span>{html.escape(heading)}</span></div>{body}<footer>{edit}</footer></main></div><script type="application/json" id="search-data">{search_json}</script><script src="{js}" defer></script></body></html>''', encoding='utf-8')
    for p in pages:
        output = OUT / p.relative_to(ROOT).with_suffix('.html')
        toc_options = {'toc_depth': '2-3'}
        if p.parent == ROOT and p.name in ('README.md', 'README.zh-CN.md', 'README.ru.md'):
            toc_options['slugify'] = slugify_unicode
        renderer = markdown.Markdown(extensions=['extra', 'toc'], extension_configs={'toc': toc_options})
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
        if p == ROOT / 'docs/evidence.md':
            data = json.loads((ROOT / 'reports/directional.json').read_text())['results']
            content += ('<section class="chart"><h2>本地吞吐测试</h2><div class="tabs">'
                        '<button data-scenario="rtt80">额外 80 ms RTT</button>'
                        '<button data-scenario="download-loss">下载丢包</button>'
                        '<button data-scenario="upload-loss">上传丢包</button>'
                        '<button data-scenario="download-cap">下载限速</button></div>'
                        '<div id="bars" aria-live="polite"></div>'
                        '<p>每个方向传输 3 次，每次 2 MiB，取吞吐量中位数。</p></section>'
                        '<script type="application/json" id="bench-data">'
                        + json.dumps(data).replace('<', '\\u003c') + '</script>')
        shell(output, title(p), '<article class="article">' + content + '</article>', p)
    # Both files live at the same depth, so all relative URLs stay valid.
    shutil.copyfile(OUT / 'README.zh-CN.html', OUT / 'index.html')
    # Remove earlier editions of this site's generated pages when rebuilding in place.
    expected = {OUT / p.relative_to(ROOT).with_suffix('.html') for p in pages}
    for old in (OUT / 'docs').rglob('*.html'):
        if old not in expected and 'id="search-data"' in old.read_text(encoding='utf-8'):
            old.unlink()
    print(f'Built {len(pages)+1} pages with local assets and validated relative links')


if __name__ == '__main__':
    main()
