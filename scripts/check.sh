#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 - "$ROOT" << 'PY'
import json
import sys
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

root = Path(sys.argv[1])
docs = root / "docs"
errors = []

def fail(message):
    errors.append(message)

pages = {
    "index.html": "https://www.boltforgegaming.com/",
    "builds.html": "https://www.boltforgegaming.com/builds",
    "custom-build.html": "https://www.boltforgegaming.com/custom-build",
    "services.html": "https://www.boltforgegaming.com/upgrades-service",
    "book.html": "https://www.boltforgegaming.com/book",
    "about.html": "https://www.boltforgegaming.com/about",
}

approved_starting = {
    "2,957", "3,858", "4,674", "10,292",
    "2,850", "3,751", "4,567", "10,185",
}

root_images = [
    "hero.jpg", "lineup.jpg", "showroom.jpg",
    "tier-core.jpg", "tier-pro.jpg", "tier-pro-max.jpg", "tier-ultra.jpg",
]

for name in root_images:
    if not (root / name).is_file():
        fail(f"root image missing: {name}")
    if (docs / name).exists():
        fail(f"root image was copied into docs: {name}")

if any(root.rglob("CNAME")):
    fail("CNAME file is present")

for path in docs.rglob("*"):
    if path.is_file() and b"sister" in path.read_bytes().lower():
        fail(f"{path.relative_to(root)} contains 'sister'")

class Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs = []
        self.ids = set()
        self.robots = []
        self.canonical = []
        self.text_parts = []
        self.json_ld = []
        self._skip = 0
        self._in_json = False
        self._json = []

    def handle_starttag(self, tag, attrs):
        attr = {key.lower(): value or "" for key, value in attrs}
        if attr.get("id"):
            self.ids.add(attr["id"])
        if tag == "script" and attr.get("type") == "application/ld+json":
            self._in_json = True
            self._json = []
        if tag in {"script", "style"}:
            self._skip += 1
        for key in ("href", "src"):
            if attr.get(key):
                self.refs.append(attr[key])
        if tag == "meta" and attr.get("name", "").lower() == "robots":
            self.robots.append(attr.get("content", ""))
        if tag == "link" and attr.get("rel", "").lower() == "canonical":
            self.canonical.append(attr.get("href", ""))

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._skip:
            self._skip -= 1
        if tag == "script" and self._in_json:
            self.json_ld.append("".join(self._json))
            self._in_json = False

    def handle_data(self, data):
        if self._in_json:
            self._json.append(data)
        elif not self._skip:
            self.text_parts.append(data)

def local_target(page, ref):
    if ref.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None, ""
    parsed = urlparse(ref)
    fragment = parsed.fragment
    if parsed.scheme in {"http", "https"}:
        prefix = "https://boltforgegaming.github.io/boltforge-media/"
        if ref.startswith(prefix):
            relative = unquote(parsed.path.removeprefix("/boltforge-media/"))
            return docs / relative, fragment
        return None, fragment
    if ref.startswith("//"):
        return None, fragment
    if parsed.path.startswith("/"):
        fail(f"{page.name}: root-absolute link {ref}")
        return None, fragment
    if not parsed.path:
        return page, fragment
    return (page.parent / unquote(parsed.path)).resolve(), fragment

parsed_pages = {}
for filename, canonical in pages.items():
    page = docs / filename
    if not page.is_file():
        fail(f"missing page {filename}")
        continue
    raw = page.read_text()
    if "markup" in raw.lower():
        fail(f"{filename} mentions markup")
    for phrase in ("Assembly is a flat $149", "$X,XXX", "parts-cost", "parts cost formula"):
        if phrase in raw:
            fail(f"{filename} has stale copy: {phrase}")
    for match in re.finditer(r"Starting at \$([0-9]{1,3}(?:,[0-9]{3})*)", raw):
        if match.group(1) not in approved_starting:
            fail(f"{filename} has unapproved starting price ${match.group(1)}")
    collector = Collector()
    collector.feed(raw)
    parsed_pages[filename] = collector
    if collector.robots != ["noindex"]:
        fail(f"{filename} robots meta is {collector.robots!r}")
    if collector.canonical != [canonical]:
        fail(f"{filename} canonical is {collector.canonical!r}")
    if 'href="css/site.css"' not in raw:
        fail(f"{filename} missing css/site.css")
    for ref in collector.refs:
        if ref.startswith("#"):
            fragment = ref[1:]
            if fragment and fragment not in collector.ids:
                fail(f"{filename} missing #{fragment}")
            continue
        target, fragment = local_target(page, ref)
        if target is None:
            continue
        if not target.is_file():
            fail(f"{filename} missing asset {ref}")
            continue
        if fragment and target.suffix == ".html":
            linked = parsed_pages.get(target.name)
            if linked is None:
                linked = Collector()
                linked.feed(target.read_text())
            if fragment not in linked.ids:
                fail(f"{filename} links to missing #{fragment} in {target.name}")

index = (docs / "index.html").read_text()
builds = (docs / "builds.html").read_text()
custom = (docs / "custom-build.html").read_text()
for phrase in (
    "Founder assembly just $149 (save $107, tax included)",
    "Buddy Plan: assembly just $99 each (save $160 each, tax included)",
    "Discord Founder role",
    "Not combinable.",
    "through November 2",
    "November 3",
):
    if phrase not in index or phrase not in builds:
        fail(f"missing offer copy on home or builds: {phrase}")

for amount in ("2,957", "3,858", "4,674", "10,292", "2,850", "3,751", "4,567", "10,185"):
    needle = f"Starting at ${amount} · Tax included"
    if needle not in index:
        fail(f"index.html missing {needle}")
for amount in ("2,957", "3,858", "4,674", "10,292"):
    needle = f"Starting at ${amount} · Tax included"
    if needle not in builds:
        fail(f"list price missing on builds: {needle}")
for amount in ("3,858", "4,674"):
    needle = f"From ${amount} · Tax included"
    if needle not in custom:
        fail(f"list price missing on custom build: {needle}")

about = parsed_pages["about.html"]
for section in ("about", "faq", "warranty", "contact", "privacy", "walkin"):
    if section not in about.ids:
        fail(f"about.html missing #{section}")

css = (docs / "css/site.css").read_text()
compact = re.sub(r"\s+", "", css)
if "#walkin{display:none;}" not in compact or "#walkin:target{display:block;}" not in compact:
    fail("walk-in section is not hidden except for its hash")

faq_blocks = []
for block in about.json_ld:
    data = json.loads(block)
    kind = data.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    if "FAQPage" in kinds:
        faq_blocks.append(data)
if len(faq_blocks) != 1:
    fail(f"expected one FAQPage schema, found {len(faq_blocks)}")
else:
    visible = "".join(about.text_parts)
    for item in faq_blocks[0]["mainEntity"]:
        if item["name"] not in visible:
            fail("FAQ question missing: " + item["name"])
        if item["acceptedAnswer"]["text"] not in visible:
            fail("FAQ answer does not match schema: " + item["name"])

for filename, collector in parsed_pages.items():
    found = False
    for block in collector.json_ld:
        data = json.loads(block)
        kind = data.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "ComputerStore" in kinds and "LocalBusiness" in kinds:
            found = True
    if not found:
        fail(f"{filename} missing LocalBusiness/ComputerStore schema")

about_raw = (docs / "about.html").read_text()
for token in (
    "https://crm.zoho.com/crm/WebToLeadForm",
    "02c8cb874b16909a2eaf3e6381781ec18ca76896739f6a46a11021aae1c24806",
    "d915922e9746ebc0eb4af2542803be12f084ade3803231df7a84908870a447972e0203723c60d829b7b74f2aadf83115",
    "webform7617033000000634315",
    "ce753cc8ef7168ef64ed69f05eaa106233db27b251ae95c3d94e50b1baa6a48f",
    "cf2977f8ab662b7b2d6ed272ac0c7faeccca1ae5c78fd4118439b4fd2f65d06607726cf73dbbab1dcf5dbc12f118af27",
    "webform7617033000000634788",
):
    if token not in about_raw:
        fail("about.html lost a Zoho form field")
if 'id="bf-configurator"' not in custom:
    fail("custom-build.html is missing the configurator")
if "e8059e15eb56abe0ea3dd4d91c4d8638f3832195762af298ff50f295a6132f8c" not in custom:
    fail("configurator lost its Zoho lead token")

showroom = "the BoltForge showroom inside Boise Computer Care"
for path in sorted(docs.glob("*.html")):
    raw = path.read_text()
    for stale in ("Fairview Ave showroom", "our Boise showroom", "the Boise showroom", "our showroom"):
        if stale in raw:
            fail(f"{path.name} still says {stale!r}")
    if showroom not in raw and showroom.capitalize() not in raw and "The BoltForge showroom inside Boise Computer Care" not in raw:
        fail(f"{path.name} never names the BoltForge showroom inside Boise Computer Care")
if "<p>BoltForge Gaming is owned by BoltForge Inc, an Idaho corporation.</p>" in about_raw:
    fail("Come say hello still includes the ownership sentence")
if "owned by BoltForge Inc, an Idaho corporation. 18-month warranty" not in about_raw:
    fail("footer lost the ownership sentence")
if "is owned by BoltForge Inc, an Idaho corporation, located at" not in about_raw:
    fail("privacy policy lost the ownership sentence")

embeds = (docs / "js" / "embeds.js").read_text()
if "https://boltforgegaming.zohobookings.com/portal-embed#/boltforgegaming" not in embeds:
    fail("docs/js/embeds.js is missing the Zoho Bookings portal URL")
if "siqe62211ac8f26ff97ebbc0fff63048a1399ac0f63725b2b8517f08967f046a335" not in embeds:
    fail("docs/js/embeds.js is missing the SalesIQ widget code")
if "https://salesiq.zohopublic.com/widget?wc=" not in embeds:
    fail("docs/js/embeds.js is missing the SalesIQ widget URL")
book = (docs / "book.html").read_text()
for phrase in (
    "Book a showroom visit",
    "Showroom Visit &amp; Build Consultation",
    "Virtual Build Consultation",
    "PC Pickup &amp; Walkthrough",
    "30 min",
    "20 min",
    "the BoltForge showroom inside Boise Computer Care, 10504 W Fairview Ave, Boise ID 83704",
    "Friday–Wednesday, 10 AM–8 PM. Closed Thursday.",
    'data-bookings',
    'href="tel:+12089963502"',
    'href="about.html#contact">Get a Quote',
    'href="https://boltforgegaming.zohobookings.com/boltforgegaming">Open booking page',
):
    if phrase not in book:
        fail(f"book.html missing {phrase}")
if "once it is connected" in book:
    fail("book.html still says the calendar is not connected")
if "<iframe" in book.lower():
    fail("book.html should mount the calendar iframe from embeds.js")
for filename in pages:
    raw = (docs / filename).read_text()
    if 'src="js/embeds.js"' not in raw:
        fail(f"{filename} is missing js/embeds.js")
    if "Book a Visit" not in raw:
        fail(f"{filename} is missing the Book a Visit nav link")
    if 'class="nav-toggle"' not in raw:
        fail(f"{filename} is missing the menu button")
if 'href="book.html">Book a visit' not in index or 'class="bf-book"' not in custom:
    fail("Home or Custom Build is missing the Book a visit button")

if errors:
    print(f"{len(errors)} check(s) failed:")
    for item in errors:
        print(" -", item)
    sys.exit(1)
print("links, prices, schema, and forms ok")
PY

python3 "$ROOT/scripts/build_zoho.py" --check

VNU_JAR="${VNU_JAR:-/tmp/vnu.jar}"
if [[ ! -f "$VNU_JAR" ]]; then
  curl -fsSL -o "$VNU_JAR" "https://github.com/validator/validator/releases/download/latest/vnu.jar"
fi
java -jar "$VNU_JAR" --errors-only "$ROOT"/docs/*.html
java -jar "$VNU_JAR" --errors-only --css "$ROOT"/docs/css/site.css
echo "html ok"
