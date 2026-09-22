"""Validate the GitHub Pages static export in ./out.

Run after `npm run build:pages`:

    python scripts/validate_export.py [--base-path /market-summary] [--site-url https://coolxng.github.io/market-summary/]

Checks required routes and artifacts, resolves every internal link in every
exported HTML page against the base path, confirms manifest icons exist, and
scans the export for anything that looks like a credential.
"""

import argparse
import html.parser
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

REQUIRED = (
    "index.html",
    ".nojekyll",
    "robots.txt",
    "sitemap.xml",
    "feed.xml",
    "manifest.webmanifest",
    "sw.js",
    "offline.html",
    "icon-192.png",
    "icon-512.png",
    "icon-maskable-512.png",
    "reports/index.html",
    "reports/2026-09-18/index.html",
    "reports/2026-09-18/report.json",
    "morning/index.html",
    "search/index.html",
    "assets/nvda/index.html",
    "assets/spx/index.html",
    "assets/bitcoin/index.html",
    "assets/us-10y/index.html",
)

CONTENT = (
    ("index.html", "THE DAILY TAPE"),
    ("index.html", "What’s on the tape"),
    ("reports/2026-09-18/index.html", "ARCHIVED DAILY TAPE"),
    ("reports/index.html", "Browse the tape"),
    ("morning/index.html", "Morning Tape"),
    ("search/index.html", "Find the tape"),
)

SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"discord(?:app)?\.com/api/webhooks/\d+/[\w-]+"),
    re.compile(r"ANTHROPIC_API_KEY\s*[=:]\s*['\"][^'\"]+"),
)


class LinkCollector(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        for name in ("href", "src"):
            value = attributes.get(name)
            if value and tag in {"a", "link", "script", "img"}:
                self.links.append(value)


def resolve_target(out, base_path, page_url, link):
    parsed = urlparse(link)
    if parsed.scheme in {"http", "https", "mailto", "data", "javascript"} or link.startswith("#") or link.startswith("//"):
        return None
    absolute = urlparse(urljoin(page_url, link)).path
    if not absolute.startswith(f"{base_path}/"):
        return f"escapes base path: {link} -> {absolute}"
    relative = absolute[len(base_path) + 1:]
    candidate = out / relative
    if relative == "" or relative.endswith("/"):
        candidate = candidate / "index.html"
    if candidate.exists() or (out / relative).is_dir() and (out / relative / "index.html").exists():
        return None
    return f"missing target: {link} -> {absolute}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out")
    parser.add_argument("--base-path", default="/market-summary")
    parser.add_argument("--site-url", default="https://coolxng.github.io/market-summary/")
    args = parser.parse_args()
    out = Path(args.out)
    base = args.base_path.rstrip("/")
    problems = []

    for name in REQUIRED:
        if not (out / name).exists():
            problems.append(f"missing file: {name}")
    for name, needle in CONTENT:
        path = out / name
        if path.exists() and needle not in path.read_text(encoding="utf-8", errors="replace"):
            problems.append(f"{name} does not contain {needle!r}")

    index = (out / "index.html").read_text(encoding="utf-8") if (out / "index.html").exists() else ""
    if f"{base}/_next/" not in index:
        problems.append("index.html does not reference assets under the base path")

    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8") if (out / "sitemap.xml").exists() else ""
    for needle in (args.site_url, "reports/2026-09-18/", "/morning/", "/assets/nvda/"):
        if needle not in sitemap:
            problems.append(f"sitemap.xml missing {needle}")

    manifest_path = out / "manifest.webmanifest"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("start_url", "").startswith(f"{base}/"):
            problems.append("manifest start_url is outside the base path")
        for icon in manifest.get("icons", []):
            if not (out / icon["src"][len(base) + 1:]).exists():
                problems.append(f"manifest icon missing: {icon['src']}")

    pages = sorted(out.rglob("*.html"))
    broken = set()
    for page in pages:
        relative = page.relative_to(out).as_posix()
        page_url = f"https://example.test{base}/{relative[:-len('index.html')] if relative.endswith('index.html') else relative}"
        collector = LinkCollector()
        collector.feed(page.read_text(encoding="utf-8", errors="replace"))
        for link in collector.links:
            issue = resolve_target(out, base, page_url, link)
            if issue:
                broken.add(f"{relative}: {issue}")
    problems.extend(sorted(broken))

    for path in out.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".js", ".json", ".txt", ".xml", ".webmanifest", ".css"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    problems.append(f"possible credential in {path.relative_to(out)} ({pattern.pattern[:24]}…)")

    if problems:
        print("Static export validation failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"Static export OK: {len(REQUIRED)} required files, {len(pages)} HTML pages link-checked, no credentials found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
