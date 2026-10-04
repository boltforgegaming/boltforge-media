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
    ("about.html", "about", "About", "/about"),
    ("book.html", "book", "Book a Visit", "/book"),
)
SLUGS = {
    "index.html": "/",
    "builds.html": "/builds",
    "custom-build.html": "/custom-build",
    "services.html": "/book#services",
    "book.html": "/book",
    "about.html": "/about",
}
FONTS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&amp;family=Outfit:wght@600;700&amp;display=swap" rel="stylesheet">
"""
HIDE = """<style>
.zpheader,
.zpfooter,
.zpheader-container,
.theme-header,
.theme-footer {
  display: none !important;
}
.theme-content,
.zpcontent-container,
.zpelement-wrapper,
.zpelem-code {
  max-width: none !important;
  width: 100% !important;
  margin-left: 0 !important;
  margin-right: 0 !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
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
    body = body.replace('<script src="js/embeds.js" defer></script>\n', "")
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
    faq = [block for block in json_ld_blocks((DOCS / "about.html").read_text()) if "FAQPage" in block]
    if len(faq) != 1:
        raise SystemExit("about.html is missing FAQPage schema")
    script = (DOCS / "js" / "embeds.js").read_text().strip()
    lines = [
        "<!-- Paste into Zoho Sites header code. Hides the theme header and footer, lets the snippet run full bleed, and adds the sitewide schema, the FAQPage block, and the embed config. -->",
        HIDE.rstrip(),
        *blocks,
        *faq,
        "<script>",
        script,
        "</script>",
    ]
    return "\n".join(lines) + "\n"


def readme():
    return """# Zoho snippets

Zoho's free plan allows five pages. Paste `header-code.txt` into the site header. It hides the Zoho header and footer, lets each snippet run full bleed, and includes the sitewide schema, the FAQPage block, and the chat embed. The header script binds the phone menu when the page snippet appears, so the header can load before Zoho inserts that snippet. The Bookings calendar is static HTML in the Book a Visit snippet.

| Page | Zoho slug | Snippet |
| --- | --- | --- |
| Home | `/` | `index.html` |
| Builds | `/builds` | `builds.html` |
| Custom Build | `/custom-build` | `custom-build-part1.html`, then `custom-build-part2.html` |
| About | `/about` | `about-part1.html`, then `about-part2.html` |
| Book a Visit | `/book` | `book.html` |

The Zoho page with slug `/book` replaces the old Services page. Services and upgrades are the section at `/book#services`. Do not create a `/services` page. There is no services snippet to paste.

Custom Build is split because of Zoho's size limit. Part 1 holds the stylesheet, including the rules for the slim full-width "Not sure where to start?" rows. Part 2 holds the configurator script and those rows. Paste part 1 first so the row styles are on the page before the rows render.
"""


def build():
    files = {"header-code.txt": header_code(), "README.md": readme()}
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
                'href="book.html',
                'href="about.html',
            ):
                if stale in text:
                    raise SystemExit(f"{name} still has a docs-relative link ({stale})")
    for filename, stem, _label, _slug in PAGES:
        page_files = [text for name, text in files.items() if name == f"{stem}.html" or name.startswith(f"{stem}-part")]
        if not any(IMG in text for text in page_files):
            raise SystemExit(f"{filename} snippet is missing raw image URLs")
    header = files["header-code.txt"]
    for needle in (
        ".zpheader",
        ".zpfooter",
        ".zpheader-container",
        ".theme-header",
        ".theme-footer",
        "display: none !important",
        "max-width: none !important",
        "siqe62211ac8f26ff97ebbc0fff63048a1399ac0f63725b2b8517f08967f046a335",
        "https://salesiq.zohopublic.com/widget?wc=",
        "ComputerStore",
        "LocalBusiness",
        "FAQPage",
        'closest(".nav-toggle")',
    ):
        if needle not in header:
            raise SystemExit(f"header-code.txt is missing {needle}")
    if "mountBookings" in header or "MutationObserver" in header:
        raise SystemExit("header-code.txt still injects the booking iframe")
    part1 = files["custom-build-part1.html"]
    part2 = files["custom-build-part2.html"]
    style_end = part1.find("</style>")
    if part1.count("<style>") != 1 or style_end < 0 or ".bf-suggest-row" not in part1[:style_end]:
        raise SystemExit("custom-build part 1 does not contain a closed start-row stylesheet")
    if "<style" in part2:
        raise SystemExit("custom-build part 2 splits the stylesheet")
    if "Not sure where to start?" not in part2 or "bf-suggest-row" not in part2:
        raise SystemExit("custom-build part 2 is missing the slim start rows")
    if "Start with this build" in part1 + part2 or "bf-intro-grid" in part1 + part2:
        raise SystemExit("custom-build snippet still has the old suggestion card")
    book = "".join(text for name, text in files.items() if name == "book.html" or name.startswith("book-part"))
    if 'id="services"' not in book or "Services &amp; upgrades" not in book:
        raise SystemExit("book snippet is missing the services section")
    static_iframe = '<iframe class="bookings-frame" src="https://boltforgegaming.zohobookings.com/portal-embed#/boltforgegaming" title="Book a visit with BoltForge Gaming" loading="lazy"></iframe>'
    if book.count(static_iframe) != 1 or "or call" not in book or "not connected yet" in book:
        raise SystemExit("book snippet is missing the static Bookings iframe")
    if "services.html" in files:
        raise SystemExit("services snippet should not be generated")
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
