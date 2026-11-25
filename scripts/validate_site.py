#!/usr/bin/env python3
"""Validate the static NOVARA marketing site before GitHub Pages publication.

Standard library only, so this can run in CI with a bare
``python scripts/validate_site.py`` invocation.  Every check prints a clear
``[PASS]`` or ``[FAIL]`` line; the process exits non-zero when any check fails.
Warnings and informational notes never change the exit status.

The site is expected at ``<repo>/site``; use ``--site-dir`` to validate a copy
elsewhere.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_DIR = ROOT / "site"

REQUIRED_FILES = (
    "index.html",
    "assets/css/styles.css",
    "assets/js/site.js",
    "assets/img/novara-logo.svg",
    "assets/img/novara-logo-light.svg",
    "assets/img/favicon.svg",
    "assets/img/og-cover.png",
    "assets/img/twitter-card.png",
    "assets/img/demo-poster.png",
    "videos/NOVARA_Product_Demo_1.0.mp4",
    "videos/NOVARA_Product_Demo_2.0.mp4",
    "videos/NOVARA_QA_Evidence_Walkthrough.mp4",
    "sitemap.xml",
    "robots.txt",
)

TEXT_EXTENSIONS = {".html", ".css", ".js", ".xml", ".txt"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Both real mojibake characters and the literal escape sequence are checked.
MOJIBAKE_SEQUENCES = ("Ã", "Â", "â€", "\ufffd", "\\ufffd")

GITHUB_HOSTS = {
    "github.com",
    "www.github.com",
    "gist.github.com",
    "docs.github.com",
    "raw.githubusercontent.com",
    "githubusercontent.com",
    "www.githubusercontent.com",
}

OG_KEYS = ("og:title", "og:description", "og:image", "og:type", "og:url")
TWITTER_KEYS = ("twitter:card", "twitter:title", "twitter:description", "twitter:image")

SECRET_KEYWORD_RE = re.compile(
    r"\b(?:api[_-]?key|secret|password|passwd|private[_-]?key|token)\b",
    re.IGNORECASE,
)
QUOTED_SECRET_RE = re.compile(
    r"\b(?:api[_-]?key|secret|password|passwd|private[_-]?key|token)"
    r"\s*[:=]\s*([\"'`])([^\"'`\r\n]{8,})\1",
    re.IGNORECASE,
)
UNQUOTED_SECRET_RE = re.compile(
    r"\b(?:api[_-]?key|secret|password|passwd|private[_-]?key|token)"
    r"\s*[:=]\s*([A-Za-z0-9_\-./+=]{20,})",
    re.IGNORECASE,
)
EXPLANATORY_MARKERS = (
    "not required", "not needed", "does not", "doesn't", "is not", "isn't",
    "never", "without", "no api", "none", "null", "optional", "placeholder",
    "example", "sample", "dummy", "fake", "redacted", "omitted", "your ",
    "here", "see ", "such as", "e.g.", "todo", "xxx", "<", "{", "}",
    "for demonstration",
)


def _configure_output() -> None:
    """Make UTF-8 output safe on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except (ValueError, OSError):
                pass


def _short(text: str, limit: int = 110) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _joined(items: Iterable[str], limit: int = 8) -> str:
    items = list(items)
    if not items:
        return ""
    shown = "; ".join(items[:limit])
    if len(items) > limit:
        shown += f"; ... (+{len(items) - limit} more)"
    return shown


def _is_http_url(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("//")


def _is_within(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def _looks_like_credential(value: str) -> bool:
    """Narrow heuristic: quoted/unquoted assignments that look like a real secret."""
    value = value.strip()
    if len(value) < 12:
        return False
    lowered = value.lower()
    if any(marker in lowered for marker in EXPLANATORY_MARKERS):
        return False
    has_digit = any(char.isdigit() for char in value)
    has_symbol = any(char in "-_+/=.:" for char in value)
    has_alpha = any(char.isalpha() for char in value)
    if has_digit and has_alpha:
        return True
    return len(value) >= 20 and has_symbol and has_alpha


class Report:
    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.info_notes: list[str] = []

    def check(self, label: str, ok: bool, detail: str = "") -> None:
        suffix = f" - {detail}" if detail else ""
        if ok:
            self.passed += 1
            print(f"[PASS] {label}{suffix}")
        else:
            self.failures.append(label)
            print(f"[FAIL] {label}{suffix}")

    def fail(self, label: str, detail: str = "") -> None:
        self.check(label, False, detail)

    def warn(self, label: str, detail: str = "") -> None:
        self.warnings.append(label)
        print(f"[WARN] {label}" + (f" - {detail}" if detail else ""))

    def info(self, label: str, detail: str = "") -> None:
        self.info_notes.append(label)
        print(f"[INFO] {label}" + (f" - {detail}" if detail else ""))


def record_reference(
    attribute: str,
    value: str,
    line: int,
    local: list[tuple[str, str, int]],
    external: list[tuple[str, str, int]],
    fragments: list[tuple[str, int]],
) -> None:
    """Classify one href/src value into local file, external URL, or fragment."""
    reference = value.strip()
    if not reference:
        return
    lowered = reference.lower()
    if lowered.startswith("#"):
        fragments.append((unquote(reference[1:]), line))
        return
    if lowered.startswith(("http://", "https://", "//")):
        external.append((attribute, reference, line))
        return
    if lowered.startswith(("data:", "mailto:", "tel:", "javascript:", "blob:", "about:")):
        return
    local.append((attribute, reference, line))


class SiteParser(HTMLParser):
    """Collect the HTML facts the validator needs in a single pass."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.doctypes: list[str] = []
        self.html_lang: str | None = None
        self.meta_tags: list[dict[str, str]] = []
        self.link_tags: list[dict[str, str]] = []
        self.title_texts: list[str] = []
        self.ids: set[str] = set()
        self.local_refs: list[tuple[str, str, int]] = []
        self.external_refs: list[tuple[str, str, int]] = []
        self.fragment_refs: list[tuple[str, int]] = []
        self.script_sources: list[tuple[str, int]] = []
        self.stylesheet_hrefs: list[tuple[str, int]] = []
        self.json_ld_blocks: list[tuple[str, int]] = []
        self._title_depth = 0
        self._title_parts: list[str] = []
        self._json_depth = 0
        self._json_parts: list[str] = []
        self._json_line = 0

    def handle_decl(self, decl: str) -> None:
        self.doctypes.append(decl)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        line, _ = self.getpos()

        if tag == "html" and self.html_lang is None:
            self.html_lang = attributes.get("lang", "")
        if tag == "meta":
            self.meta_tags.append(attributes)
        if tag == "link":
            self.link_tags.append(attributes)
            if "stylesheet" in attributes.get("rel", "").lower().split():
                if attributes.get("href", "").strip():
                    self.stylesheet_hrefs.append((attributes["href"].strip(), line))
        if attributes.get("id", "").strip():
            self.ids.add(attributes["id"].strip())

        if tag == "title":
            if self._title_depth == 0:
                self._title_parts = []
            self._title_depth += 1

        if tag == "script":
            if attributes.get("src", "").strip():
                self.script_sources.append((attributes["src"].strip(), line))
            if attributes.get("type", "").strip().lower() == "application/ld+json":
                if self._json_depth == 0:
                    self._json_parts = []
                    self._json_line = line
                self._json_depth += 1

        for attribute in ("href", "src"):
            if attributes.get(attribute, "").strip():
                record_reference(
                    attribute,
                    attributes[attribute],
                    line,
                    self.local_refs,
                    self.external_refs,
                    self.fragment_refs,
                )

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._title_depth:
            self.title_texts.append("".join(self._title_parts).strip())
            self._title_depth -= 1
        if tag == "script" and self._json_depth:
            self.json_ld_blocks.append(("".join(self._json_parts), self._json_line))
            self._json_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._title_depth:
            self._title_parts.append(data)
        if self._json_depth:
            self._json_parts.append(data)

    def finish(self) -> None:
        """Flush constructs left open by malformed but parseable HTML."""
        if self._title_depth:
            self.title_texts.append("".join(self._title_parts).strip())
            self._title_depth = 0
        if self._json_depth:
            self.json_ld_blocks.append(("".join(self._json_parts), self._json_line))
            self._json_depth = 0


def meta_values(parser: SiteParser, key: str) -> list[str]:
    values: list[str] = []
    for tag in parser.meta_tags:
        name = (tag.get("name") or tag.get("property") or "").strip().lower()
        content = tag.get("content", "").strip()
        if name == key and content:
            values.append(content)
    return values


def link_href(parser: SiteParser, rel: str) -> str:
    for tag in parser.link_tags:
        if rel in tag.get("rel", "").lower().split():
            href = tag.get("href", "").strip()
            if href:
                return href
    return ""


def read_text(path: Path, label: str, report: Report) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        report.fail(f"{label} is readable UTF-8", str(exc))
        return ""


def main(argv: list[str] | None = None) -> int:
    _configure_output()
    argument_parser = argparse.ArgumentParser(
        description="Validate the static NOVARA marketing site before publishing."
    )
    argument_parser.add_argument(
        "--site-dir",
        type=Path,
        default=DEFAULT_SITE_DIR,
        help=f"site directory to validate (default: {DEFAULT_SITE_DIR})",
    )
    args = argument_parser.parse_args(argv)
    site_dir = args.site_dir.expanduser().resolve()
    report = Report()

    print("NOVARA static site validation")
    print(f"Site directory: {site_dir}")
    print("=" * 72)

    report.check("Site directory exists", site_dir.is_dir(), str(site_dir))

    index_path = site_dir / "index.html"
    html_text = ""
    if index_path.is_file():
        html_text = read_text(index_path, "index.html", report)
        if html_text:
            report.check("index.html is readable UTF-8", True, f"{len(html_text)} characters")
    else:
        report.fail("index.html exists", str(index_path))

    parser = SiteParser()
    try:
        parser.feed(html_text)
        parser.close()
        parser.finish()
    except Exception as exc:  # defensive: never crash CI on malformed markup
        report.fail("index.html parses with html.parser", f"{type(exc).__name__}: {exc}")
    else:
        report.check("index.html parses with html.parser", True)

    # --- Document metadata -------------------------------------------------
    doctype_ok = any(
        decl.strip().lower().replace(" ", "").startswith("doctypehtml")
        for decl in parser.doctypes
    )
    report.check("HTML doctype present", doctype_ok, _joined(parser.doctypes))

    lang = (parser.html_lang or "").strip().lower()
    report.check('HTML lang="en"', lang == "en", f"lang={lang or 'missing'}")

    title = parser.title_texts[0] if parser.title_texts else ""
    report.check(
        "Exactly one <title> containing NOVARA",
        len(parser.title_texts) == 1 and "novara" in title.lower(),
        f"found {len(parser.title_texts)}: {_short(title)}" if title else f"found {len(parser.title_texts)}",
    )

    descriptions = meta_values(parser, "description")
    report.check("Meta description present", bool(descriptions), _short(descriptions[0]) if descriptions else "missing")
    if descriptions:
        length = len(descriptions[0])
        if length <= 160:
            report.check("Meta description <= 160 characters (recommended)", True, f"{length} chars")
        else:
            report.warn("Meta description exceeds recommended 160 characters", f"{length} chars")

    canonical = link_href(parser, "canonical") or next(iter(meta_values(parser, "canonical")), "")
    report.check("Canonical URL present (placeholder allowed)", bool(canonical), _short(canonical) if canonical else "missing")

    for key in OG_KEYS:
        values = meta_values(parser, key)
        report.check(f"Open Graph meta {key} present", bool(values), _short(values[0]) if values else "missing")

    for key in TWITTER_KEYS:
        values = meta_values(parser, key)
        report.check(f"Twitter Card meta {key} present", bool(values), _short(values[0]) if values else "missing")

    viewports = meta_values(parser, "viewport")
    report.check("Viewport meta present", bool(viewports), _short(viewports[0]) if viewports else "missing")

    themes = meta_values(parser, "theme-color")
    report.check("theme-color meta present", bool(themes), _short(themes[0]) if themes else "missing")

    if not parser.json_ld_blocks:
        report.fail("JSON-LD structured data present", 'no <script type="application/ld+json"> block')
    else:
        for number, (block, line) in enumerate(parser.json_ld_blocks, start=1):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                report.fail(f"JSON-LD block {number} parses as JSON", f"line {line}: {exc.msg}")
            else:
                report.check(f"JSON-LD block {number} parses as JSON", True, f"line {line}")

    # --- Local references, fragments, and self-containment ----------------
    # Social preview images are local references too, even though they live in
    # meta tags rather than href/src attributes.
    for key in ("og:image", "twitter:image"):
        for value in meta_values(parser, key):
            record_reference(
                f"meta {key}", value, 0,
                parser.local_refs, parser.external_refs, parser.fragment_refs,
            )

    bad_local: list[str] = []
    checked_local: set[str] = set()
    for attribute, value, line in parser.local_refs:
        relative = unquote(urlsplit(value.split("#", 1)[0]).path)
        if not relative:
            continue
        checked_local.add(relative)
        target = (site_dir / relative).resolve()
        if not _is_within(target, site_dir):
            bad_local.append(f"{attribute}={_short(value, 50)} escapes site dir (line {line})")
        elif not target.is_file():
            bad_local.append(f"{attribute}={_short(value, 50)} missing (line {line})")
    report.check(
        "All local href/src targets exist under site/",
        not bad_local,
        _joined(bad_local) if bad_local else f"{len(checked_local)} local reference(s) checked",
    )

    missing_fragments = [
        f"#{fragment} (line {line})"
        for fragment, line in parser.fragment_refs
        if fragment and fragment not in parser.ids
    ]
    report.check(
        'All href="#id" fragments match an element id',
        not missing_fragments,
        _joined(missing_fragments)
        if missing_fragments
        else f"{len(parser.fragment_refs)} fragment link(s), {len(parser.ids)} id(s) collected",
    )

    github_links: list[str] = []
    other_external: list[str] = []
    script_and_style_refs = {(source, line) for source, line in parser.script_sources} | {
        (href, line) for href, line in parser.stylesheet_hrefs
    }
    for attribute, value, line in parser.external_refs:
        if (value, line) in script_and_style_refs:
            continue
        host = (urlsplit(value).hostname or "").lower()
        if host in GITHUB_HOSTS or host.endswith(".githubusercontent.com"):
            github_links.append(value)
        else:
            other_external.append(f"{attribute}={_short(value, 70)}")
    for value in sorted(set(github_links))[:20]:
        report.info("External GitHub link kept as informational", value)
    if len(set(github_links)) > 20:
        report.info("Additional external GitHub links omitted from output", f"{len(set(github_links)) - 20} more")
    if other_external:
        report.info("Other external references (not resolved locally)", _joined(other_external))

    bad_scripts = [f"{_short(src, 70)} (line {line})" for src, line in parser.script_sources if _is_http_url(src)]
    report.check("No external HTTP(S) <script src> URLs", not bad_scripts, _joined(bad_scripts) if bad_scripts else f"{len(parser.script_sources)} local script(s)")

    bad_styles = [f"{_short(href, 70)} (line {line})" for href, line in parser.stylesheet_hrefs if _is_http_url(href)]
    report.check("No external HTTP(S) stylesheet URLs", not bad_styles, _joined(bad_styles) if bad_styles else f"{len(parser.stylesheet_hrefs)} local stylesheet(s)")

    # --- Required assets ---------------------------------------------------
    missing_required = [rel for rel in REQUIRED_FILES if not (site_dir / rel).is_file()]
    empty_required = [
        rel for rel in REQUIRED_FILES
        if (site_dir / rel).is_file() and (site_dir / rel).stat().st_size == 0
    ]
    report.check(
        "All required site files exist and are non-empty",
        not missing_required and not empty_required,
        _joined(
            [f"missing: {item}" for item in missing_required]
            + [f"empty: {item}" for item in empty_required]
        ) or f"{len(REQUIRED_FILES)} file(s) checked",
    )

    bad_pngs: list[str] = []
    for relative in REQUIRED_FILES:
        if not relative.lower().endswith(".png"):
            continue
        path = site_dir / relative
        if not path.is_file():
            bad_pngs.append(f"{relative}: missing")
            continue
        with path.open("rb") as handle:
            signature = handle.read(8)
        if signature != PNG_SIGNATURE:
            bad_pngs.append(f"{relative}: invalid signature")
    report.check("PNG assets have valid PNG signatures", not bad_pngs, _joined(bad_pngs) if bad_pngs else "3 PNG(s) checked")

    for video_name in ("NOVARA_Product_Demo_1.0.mp4", "NOVARA_Product_Demo_2.0.mp4",
                       "NOVARA_QA_Evidence_Walkthrough.mp4"):
        video_path = site_dir / "videos" / video_name
        video_size = video_path.stat().st_size if video_path.is_file() else 0
        report.check(f"{video_name} is non-zero size", video_size > 0, f"{video_size} bytes")

    # --- Text-file content scans ------------------------------------------
    text_files = sorted(
        path for path in site_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS
    )
    report.check("Text files found under site/", bool(text_files), f"{len(text_files)} file(s)")

    mojibake_hits: list[str] = []
    secret_hits: list[str] = []
    keyword_mentions = 0
    for path in text_files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            mojibake_hits.append(f"{path.relative_to(site_dir).as_posix()}: invalid UTF-8 ({exc})")
            continue
        lowered_lines = [line.lower() for line in text.splitlines()]
        for line_number, (line, lowered) in enumerate(zip(text.splitlines(), lowered_lines), start=1):
            for sequence in MOJIBAKE_SEQUENCES:
                position = lowered.find(sequence.lower())
                if position >= 0:
                    snippet = line[max(0, position - 20): position + 40].replace("\t", " ")
                    mojibake_hits.append(
                        f"{path.relative_to(site_dir).as_posix()}:{line_number}: {_short(snippet, 70)}"
                    )
            keyword_mentions += len(SECRET_KEYWORD_RE.findall(line))
            for match in QUOTED_SECRET_RE.finditer(line):
                if _looks_like_credential(match.group(2)):
                    secret_hits.append(
                        f"{path.relative_to(site_dir).as_posix()}:{line_number}: {_short(match.group(2), 40)}"
                    )
            for match in UNQUOTED_SECRET_RE.finditer(line):
                if _looks_like_credential(match.group(1)):
                    secret_hits.append(
                        f"{path.relative_to(site_dir).as_posix()}:{line_number}: {_short(match.group(1), 40)}"
                    )

    report.check("No mojibake sequences in site text files", not mojibake_hits, _joined(mojibake_hits) if mojibake_hits else f"{len(text_files)} file(s) scanned")
    report.check("No credential-like secrets in site text files", not secret_hits, _joined(secret_hits) if secret_hits else f"{len(text_files)} file(s) scanned")
    report.info("Secret keyword mentions reviewed (explanatory text allowed)", f"{keyword_mentions} mention(s)")

    # --- Sitemap and robots ------------------------------------------------
    sitemap_text = read_text(site_dir / "sitemap.xml", "sitemap.xml", report)
    robotstxt_text = read_text(site_dir / "robots.txt", "robots.txt", report)

    if canonical:
        candidates = {canonical, canonical.rstrip("/")}
        report.check(
            "sitemap.xml contains the canonical URL",
            any(candidate and candidate in sitemap_text for candidate in candidates),
            _short(canonical),
        )
    else:
        report.check("sitemap.xml contains the canonical URL", False, "canonical URL unavailable")

    sitemap_line = re.search(r"(?im)^\s*sitemap\s*:\s*\S+", robotstxt_text)
    report.check(
        "robots.txt contains a Sitemap directive",
        bool(sitemap_line),
        _short(sitemap_line.group(0)) if sitemap_line else "no Sitemap: line found",
    )

    # --- Summary -----------------------------------------------------------
    print("=" * 72)
    print(
        f"Summary: {report.passed} passed, {len(report.failures)} failed, "
        f"{len(report.warnings)} warning(s), {len(report.info_notes)} informational note(s)"
    )
    if report.failures:
        print("Failed checks:")
        for failure in report.failures:
            print(f"  - {failure}")
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
