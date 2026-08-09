#!/usr/bin/env python3
"""把 PRESENTATION.md（Marp 格式）轉成可瀏覽的 HTML 簡報。

使用方式：
    python3 scripts/build_slides.py
產生：
    presentation.html（單一檔案，瀏覽器開啟即可，支援左右鍵換頁）
"""
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "PRESENTATION.md"
OUT = ROOT / "presentation.html"

MD = markdown.Markdown(extensions=["tables", "fenced_code"])

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>用 opencode 開發 flight-price-tracker</title>
<style>
  :root {
    --bg: #f7f8fa; --fg: #1f2328; --accent: #0969da; --muted: #656d76;
    --border: #d0d7de; --code-bg: #eff1f3;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; }
  body {
    background: var(--bg); color: var(--fg);
    font-family: "Segoe UI", "Noto Sans TC", "Microsoft JhengHei", Arial, sans-serif;
    overflow: hidden;
  }
  .deck { width: 100%; height: 100%; position: relative; }
  .slide {
    position: absolute; inset: 0;
    display: none; padding: 7vh 9vw;
    overflow-y: auto; flex-direction: column; justify-content: center;
  }
  .slide.active { display: flex; }
  .slide-inner { width: 100%; max-width: 1080px; margin: 0 auto; }
  h1 { font-size: 2.6em; color: var(--accent); margin: 0 0 .3em; }
  h2 { font-size: 1.9em; margin: 0 0 .6em; border-bottom: 3px solid var(--accent);
       padding-bottom: .25em; }
  h3 { font-size: 1.35em; margin: 1em 0 .4em; }
  p, li { font-size: 1.15em; line-height: 1.65; }
  ul { padding-left: 1.3em; }
  li { margin: .45em 0; }
  table { border-collapse: collapse; margin: 1em 0; width: 100%; font-size: 1.05em; }
  th, td { border: 1px solid var(--border); padding: .55em .8em; text-align: left; }
  th { background: var(--code-bg); }
  code { background: var(--code-bg); padding: .12em .35em; border-radius: 4px;
         font-family: "Cascadia Code", Consolas, monospace; font-size: .95em; }
  pre { background: var(--code-bg); padding: 1em 1.2em; border-radius: 8px;
        overflow-x: auto; font-size: .95em; line-height: 1.5; }
  pre code { background: none; padding: 0; }
  blockquote { border-left: 4px solid var(--accent); margin: 1em 0;
               padding: .3em 1em; background: #eef4fd; border-radius: 0 8px 8px 0; }
  blockquote p { font-size: 1.25em; font-weight: 600; }
  .nav {
    position: fixed; bottom: 1.5vh; right: 2vw;
    color: var(--muted); font-size: .95em; z-index: 10;
  }
  .page { margin-right: .8em; }
  .hint { position: fixed; bottom: 1.5vh; left: 2vw; color: var(--muted);
          font-size: .85em; z-index: 10; }
  .controls button {
    border: 1px solid var(--border); background: #fff; color: var(--fg);
    border-radius: 6px; padding: .25em .7em; font-size: 1em; cursor: pointer;
  }
  @media print {
    body { overflow: visible; }
    .slide { position: relative; display: flex !important; page-break-after: always;
             min-height: 100vh; }
    .nav, .hint { display: none; }
  }
</style>
</head>
<body>
<div class="deck">
{slides}
</div>
<div class="nav">
  <button class="controls" data-nav="prev">◀</button>
  <span class="page"><span id="cur">1</span> / <span id="total">{total}</span></span>
  <button class="controls" data-nav="next">▶</button>
</div>
<div class="hint">← → 換頁 ・ F11 全螢幕 ・ 列印可輸出 PDF</div>
<script>
  const slides = document.querySelectorAll('.slide');
  let cur = 0;
  function show(i) {
    cur = Math.max(0, Math.min(slides.length - 1, i));
    slides.forEach((s, k) => s.classList.toggle('active', k === cur));
    document.getElementById('cur').textContent = cur + 1;
    document.querySelector('.slide.active')?.scrollTo(0, 0);
  }
  window.addEventListener('keydown', e => {
    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); show(cur + 1); }
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); show(cur - 1); }
    if (e.key === 'Home') show(0);
    if (e.key === 'End') show(slides.length - 1);
  });
  document.querySelectorAll('[data-nav]').forEach(b =>
    b.addEventListener('click', () => show(cur + (b.dataset.nav === 'next' ? 1 : -1))));
</script>
</body>
</html>
"""


def split_slides(text: str) -> list[str]:
    """依『---』分隔投影片；跳過最前面的 front matter 與程式碼區塊。"""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        idx = 1
        while idx < len(lines) and lines[idx].strip() != "---":
            idx += 1
        lines = lines[idx + 1:]
    slides: list[str] = []
    buf: list[str] = []
    fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            fence = not fence
        if stripped == "---" and not fence:
            if buf:
                slides.append("\n".join(buf))
                buf = []
            continue
        buf.append(line)
    if buf:
        slides.append("\n".join(buf))
    return slides


def clean_slide(text: str) -> str:
    """移除 Marp 專用指令（如 <!-- _paginate: false -->）。"""
    out = []
    for line in text.splitlines():
        if re.match(r"^\s*<!--", line):
            continue
        out.append(line)
    return "\n".join(out)


def build() -> None:
    raw = SRC.read_text(encoding="utf-8")
    slides = [clean_slide(s) for s in split_slides(raw)]
    rendered = []
    for idx, s in enumerate(slides, 1):
        body = MD.reset().convert(s)
        rendered.append(
            f'<section class="slide{" active" if idx == 1 else ""}">'
            f'<div class="slide-inner">{body}</div></section>'
        )
    html = HTML_TEMPLATE.replace("{slides}", "\n".join(rendered)).replace(
        "{total}", str(len(slides))
    )
    OUT.write_text(html, encoding="utf-8")
    print(f"已產生 {OUT}（{len(slides)} 頁）")


if __name__ == "__main__":
    build()
