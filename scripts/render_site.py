#!/usr/bin/env python3

import html
import sys
from pathlib import Path

import markdown


ROOT = Path(__file__).resolve().parents[1]
MAIN_MD = ROOT / "exposome.md"


CSS = """
:root {
  --bg: #f7f8fb;
  --fg: #1f2937;
  --heading: #111827;
  --surface: #ffffff;
  --link: #0f62fe;
  --border: #e5e7eb;
  --muted: #4b5563;
  --code-bg: #f3f4f6;
  --blockquote-bg: #f9fafb;
  --blockquote-border: #d1d5db;
  --table-header: #f9fafb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111827;
    --fg: #e5e7eb;
    --heading: #f9fafb;
    --surface: #1f2937;
    --link: #60a5fa;
    --border: #374151;
    --muted: #9ca3af;
    --code-bg: #374151;
    --blockquote-bg: #1f2937;
    --blockquote-border: #4b5563;
    --table-header: #1f2937;
  }
}
*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 16px/1.7 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
a.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--link);
  color: #fff;
  padding: 8px 16px;
  z-index: 100;
  transition: top 0.2s;
}
a.skip-link:focus { top: 0; }
main {
  max-width: 920px;
  margin: 0 auto;
  padding: 48px 24px 80px;
  background: var(--surface);
  min-height: 100vh;
}
h1, h2, h3, h4 { color: var(--heading); line-height: 1.25; }
h1 { font-size: 2.2rem; margin-top: 0; }
h2 { margin-top: 2.2rem; padding-top: 0.4rem; border-top: 1px solid var(--border); }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
code { background: var(--code-bg); padding: 0.1rem 0.35rem; border-radius: 4px; }
blockquote {
  margin: 1rem 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid var(--blockquote-border);
  background: var(--blockquote-bg);
}
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid var(--border); padding: 0.6rem 0.8rem; text-align: left; }
th { background: var(--table-header); }
ul, ol { padding-left: 1.4rem; }
nav[aria-label="Monthly archive"] { margin-top: 1rem; }
.site-header {
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}
.site-header p {
  margin: 0.4rem 0 0;
  color: var(--muted);
}
footer {
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  font-size: 0.85rem;
  color: var(--muted);
}
"""


def render_markdown_file(source_path, output_path, title):
    if not source_path.exists():
        print(f"  Warning: {source_path} not found, skipping", file=sys.stderr)
        return

    body = markdown.markdown(
        source_path.read_text(),
        extensions=["extra", "toc", "sane_lists"],
        output_format="html5",
        extension_configs={
            "toc": {"toc_depth": "2-3"},
        },
    )
    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light dark" />
  <title>{html.escape(title)}</title>
  <style>{CSS}</style>
</head>
<body>
  <a class="skip-link" href="#content">Skip to content</a>
  <main id="content">
    <header class="site-header" role="banner">
      <strong>Exposome</strong>
      <p>Static textbook-style chapter with monthly literature updates.</p>
    </header>
    <article>
      {body}
    </article>
    <footer>
      <p>Generated from <a href="https://github.com">source repository</a>. Content is machine-managed with monthly updates.</p>
    </footer>
  </main>
</body>
</html>
"""
    output_path.write_text(document)


def main():
    if not MAIN_MD.exists():
        print(f"Main markdown file not found: {MAIN_MD}", file=sys.stderr)
        sys.exit(1)

    render_markdown_file(MAIN_MD, ROOT / "index.html", "Exposome")
    render_markdown_file(MAIN_MD, ROOT / "exposome.html", "Exposome")

    updates_dir = ROOT / "updates"
    if updates_dir.exists():
        for markdown_path in sorted(updates_dir.glob("*.md")):
            if markdown_path.name == ".gitkeep":
                continue
            render_markdown_file(
                markdown_path, markdown_path.with_suffix(".html"), markdown_path.stem
            )
    print("Rendered HTML pages")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"render_site.py failed: {exc}", file=sys.stderr)
        raise
