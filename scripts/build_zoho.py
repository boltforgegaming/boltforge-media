#!/usr/bin/env python3
"""Write paste-ready Zoho Sites snippets from docs/."""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = ROOT / "zoho"
LIMIT = 60_000
IMG = "https://raw.githubusercontent.com/boltforgegaming/boltforge-media/main/docs/img/"
PAGES = (
    ("index.html", "index", "Home", "/"),
    ("builds.html", "builds", "Builds", "/builds"),
    ("custom-build.html", "custom-build", "Custom Build", "/custom-build"),
    ("services.html", "services", "Services", "/services"),
    ("about.html", "about", "About", "/about"),
)
SLUGS = {
    "index.html": "/",
    "builds.html": "/builds",
    "custom-build.html": "/custom-build",
    "services.html": "/services",
    "about.html": "/about",
}
FONTS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&amp;family=Outfit:wght@600;700&amp;display=swap" rel="stylesheet">
"""
HIDE = """<style>
.theme-header,
.theme-footer {
  display: none !important;
}
</style>
"""


def rewrite(html):
    def repl(match):
        attr, quote, url = match.group(1), match.group(2), match.group(3)
        for name, slug in SLUGS.items():
            if url == name or url.startswith(name + "#"):
                url = slug + url[len(name):]
                break
        if url.startswith("img/"):
            url = IMG + url[len("img/"):]
        return f"{attr}={quote}{url}{quote}"

    return re.sub(r"\b(href|src)=([\"'])([^\"']+)\2", repl, html)


def json_ld_blocks(html):
    return re.findall(r"<script type=\"application/ld\+json\">.*?</script>", html, flags=re.S)


def page_snippet(filename, label, slug):
    html = (DOCS / filename).read_text()
    start = html.index('<a class="skip"')
    end = html.index("</footer>", start) + len("</footer>")
    body = rewrite(html[start:end])
    faq = "\n".join(block for block in json_ld_blocks(html) if "FAQPage" in block)
    css = (DOCS / "css" / "site.css").read_text().strip()
    parts = [
        f"<!-- BoltForge Zoho snippet: {label} ({slug}). Paste into a code element on that page. -->",
        FONTS.rstrip(),
        "<style>",
        css,
        "</style>",
    ]
    if faq:
        parts.append(rewrite(faq))
    parts.append(body)
    return "\n".join(parts) + "\n"


def split_snippet(name, text):
    if len(text) <= LIMIT:
        return {f"{name}.html": text}
    points = [match.start() for match in re.finditer(r"\n(?=<section|</section>|<script|</script>|<footer|</main>)", text)]
    choices = [
        point for point in points
        if point > 0 and len(text[:point]) <= LIMIT and len(text[point:]) <= LIMIT and "<style>" in text[:point]
    ]
    if not choices:
        raise SystemExit(f"{name} is {len(text)} characters and cannot be split under {LIMIT}")
    point = max(choices)
    first = text[:point]
    if not first.endswith("\n"):
        first += "\n"
    second = text[point:].lstrip("\n")
    note = f"<!-- {name} part 2 of 2. Paste this code element after part 1. -->\n"
    first = first.replace(
        f"<!-- BoltForge Zoho snippet: ",
        f"<!-- BoltForge Zoho snippet part 1 of 2: ",
        1,
    )
    return {
        f"{name}-part1.html": first,
        f"{name}-part2.html": note + second if second.endswith("\n") else note + second + "\n",
    }


def header_code():
    html = (DOCS / "index.html").read_text()
    blocks = [block for block in json_ld_blocks(html) if "FAQPage" not in block]
    if len(blocks) < 2:
        raise SystemExit("index.html is missing sitewide schema")
    lines = [
        "<!-- Paste into Zoho Sites header code. Hides the theme header and footer and adds the sitewide schema. -->",
        HIDE.rstrip(),
        *blocks,
    ]
    return "\n".join(lines) + "\n"


def build():
    files = {"header-code.txt": header_code()}
    for filename, stem, label, slug in PAGES:
        files.update(split_snippet(stem, page_snippet(filename, label, slug)))
    for name, text in files.items():
        if len(text) > LIMIT:
            raise SystemExit(f"{name} is {len(text)} characters, over {LIMIT}")
        if name.endswith(".html"):
            for stale in (
                'src="img/',
                'href="index.html',
                'href="builds.html',
                'href="custom-build.html',
                'href="services.html',
                'href="about.html',
            ):
                if stale in text:
                    raise SystemExit(f"{name} still has a docs-relative link ({stale})")
    for filename, stem, _label, _slug in PAGES:
        page_files = [text for name, text in files.items() if name == f"{stem}.html" or name.startswith(f"{stem}-part")]
        if not any(IMG in text for text in page_files):
            raise SystemExit(f"{filename} snippet is missing raw image URLs")
    header = files["header-code.txt"]
    for needle in (".theme-header", ".theme-footer", "display: none !important", "ComputerStore", "LocalBusiness"):
        if needle not in header:
            raise SystemExit(f"header-code.txt is missing {needle}")
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = build()
    if args.check:
        errors = []
        for name, text in files.items():
            path = OUT / name
            if not path.is_file() or path.read_text() != text:
                errors.append(name)
        extra = sorted(path.name for path in OUT.glob("*") if path.name not in files) if OUT.is_dir() else []
        if errors or extra:
            print("zoho/ does not match docs/. Run: python3 scripts/build_zoho.py")
            for name in errors:
                print(" - stale", name)
            for name in extra:
                print(" - extra", name)
            return 1
        print("zoho snippets match docs")
        return 0
    OUT.mkdir(exist_ok=True)
    for path in OUT.iterdir():
        if path.name not in files:
            path.unlink()
    for name, text in files.items():
        (OUT / name).write_text(text)
        print(f"{name} {len(text)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
