#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Turn TERMS.md, PRIVACY.md and RULES.md into the Porchlite legal website.

Standard library only, so Cloudflare Pages can run it as the build command:

    python3 deploy/personal-18plus/legal/build.py

The pages land in legal/site/ (index.html, terms.html, privacy.html,
rules.html). Cloudflare Pages serves terms.html at /terms.
Anything still written as <!-- a note --> in the Markdown shows up on the page
highlighted as [a note], so a missing detail is easy to spot.
"""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "site"
LOGO = HERE.parent / "branding" / "porchlite-favicon.svg"

PAGES = [
    ("terms", "TERMS.md", "Terms of use"),
    ("privacy", "PRIVACY.md", "Privacy"),
    ("rules", "RULES.md", "Community rules"),
]
LINKS = {"TERMS.md": "terms", "PRIVACY.md": "privacy", "RULES.md": "rules"}


def inline(text: str) -> str:
    notes: list[str] = []

    def keep_note(m: re.Match) -> str:
        notes.append(m.group(1).strip())
        return f"\x00{len(notes) - 1}\x00"

    text = re.sub(r"<!--(.*?)-->", keep_note, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])_(.+?)_(?!\w)", r"<em>\1</em>", text)

    def link(m: re.Match) -> str:
        label, href = m.group(1), m.group(2)
        href = LINKS.get(href, href)
        return f'<a href="{html.escape(href)}">{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"\b([\w.+-]+@[\w-]+\.[\w.]+)\b", r'<a href="mailto:\1">\1</a>', text)
    return re.sub(r"\x00(\d+)\x00", lambda m: f'<mark>[{html.escape(notes[int(m.group(1))])}]</mark>', text)


def markdown(source: str) -> tuple[str, str]:
    """Return (title, body html) for the small Markdown subset the templates use."""
    title = ""
    out: list[str] = []
    para: list[str] = []
    items: list[str] = []
    quote: list[str] = []

    def flush() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()
        if quote:
            out.append(f"<blockquote><p>{inline(' '.join(quote))}</p></blockquote>")
            quote.clear()

    for raw in source.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
        elif line.startswith("# "):
            flush()
            title = line[2:].strip()
        elif line.startswith("## "):
            flush()
            out.append(f"<h2>{inline(line[3:].strip())}</h2>")
        elif line.startswith("- "):
            if para or quote:
                flush()
            items.append(line[2:].strip())
        elif line.startswith("> "):
            if para or items:
                flush()
            quote.append(line[2:].strip())
        elif items and raw.startswith("  "):
            items[-1] += " " + line.strip()
        else:
            if items or quote:
                flush()
            para.append(line.strip())
    flush()
    return title, "\n".join(out)


STYLE = """
:root{--bg:#f7f1e3;--card:#fffaf0;--text:#3a3327;--muted:#7a6e5a;--line:#e6dcc6;--accent:#a35e59;--honey:#b9822f;--mark:#ffe3a3}
@media (prefers-color-scheme:dark){:root{--bg:#171b15;--card:#1f241c;--text:#ece4d2;--muted:#a59d8a;--line:#33392d;--accent:#dba6a1;--honey:#d9a95b;--mark:#5a4720}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
body::before{content:"";position:fixed;inset:0 0 auto;height:320px;pointer-events:none;background:radial-gradient(60% 100% at 50% 0,color-mix(in srgb,var(--honey) 16%,transparent),transparent)}
header,main,footer{position:relative;max-width:46rem;margin:0 auto;padding:0 16px}
header{display:flex;align-items:center;gap:12px;padding-top:28px;padding-bottom:8px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px;color:var(--text);text-decoration:none;font:600 1.25rem/1 Georgia,"Iowan Old Style",serif;margin-right:auto}
.brand img{width:36px;height:36px;border-radius:9px}
nav{display:flex;gap:4px;flex-wrap:wrap}
nav a{color:var(--muted);text-decoration:none;padding:6px 10px;border-radius:999px;font-size:.95rem}
nav a:hover{color:var(--text);background:var(--line)}
nav a[aria-current]{color:var(--text);background:var(--card);box-shadow:inset 0 0 0 1px var(--line)}
main{padding-top:12px;padding-bottom:24px}
article{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:28px clamp(18px,5vw,44px)}
h1{font:600 clamp(1.7rem,5vw,2.3rem)/1.2 Georgia,"Iowan Old Style",serif;margin:0 0 4px}
h2{font:600 1.25rem/1.3 Georgia,"Iowan Old Style",serif;margin:1.8em 0 .4em;color:var(--honey)}
p,ul{margin:.6em 0}
ul{padding-left:1.25em}
li{margin:.3em 0}
li::marker{color:var(--honey)}
a{color:var(--accent);text-underline-offset:2px}
em{color:var(--muted)}
blockquote{margin:1em 0;padding:.4em 1em;border-left:3px solid var(--honey);color:var(--muted)}
mark{background:var(--mark);color:inherit;padding:0 3px;border-radius:4px}
.cards{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));margin-top:20px}
.cards a{display:block;padding:18px;border:1px solid var(--line);border-radius:14px;text-decoration:none;color:var(--text);background:var(--bg)}
.cards a:hover{border-color:var(--honey)}
.cards strong{display:block;font:600 1.1rem Georgia,serif;margin-bottom:4px}
.cards span{color:var(--muted);font-size:.95rem}
footer{color:var(--muted);font-size:.9rem;padding-bottom:36px;text-align:center}
"""


def page(slug: str, title: str, body: str, heading: str) -> str:
    nav = "".join(
        f'<a href="{s}"{" aria-current=page" if s == slug else ""}>{html.escape(label)}</a>'
        for s, _, label in PAGES
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="Porchlite is a private, adults-only (18+) chat community.">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="logo.svg" type="image/svg+xml">
<style>{STYLE}</style>
</head>
<body>
<header>
<a class="brand" href="./"><img src="logo.svg" alt="">Porchlite</a>
<nav>{nav}</nav>
</header>
<main><article>
<h1>{html.escape(heading)}</h1>
{body}
</article></main>
<footer>Porchlite · 18+ only · <a href="https://porchlite.xyz">Open Porchlite</a></footer>
</body>
</html>
"""


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    if LOGO.exists():
        shutil.copy(LOGO, OUT / "logo.svg")
    for slug, src, label in PAGES:
        heading, body = markdown((HERE / src).read_text())
        heading = heading.split(":", 1)[-1].strip().capitalize() or label
        (OUT / f"{slug}.html").write_text(page(slug, f"{label} · Porchlite", body, heading))
    cards = "".join(
        f'<a href="{s}"><strong>{html.escape(label)}</strong><span>{blurb}</span></a>'
        for (s, _, label), blurb in zip(PAGES, [
            "What you agree to when you join.",
            "What we store and who can see it.",
            "How we treat each other here.",
        ])
    )
    intro = ("<p>Porchlite is a private, adults-only (18+) chat community. Everyone gives their date of birth "
             "at sign-up and every account is approved by a person, so every community here is "
             "adults-only.</p>"
             f'<div class="cards">{cards}</div>')
    (OUT / "index.html").write_text(page("", "Porchlite · Terms, privacy and rules", intro, "The small print"))
    print(f"Built {len(PAGES) + 1} pages in {OUT}")


if __name__ == "__main__":
    main()
