#!/usr/bin/env python3
# SCRIPT: check-doc-assets
# DESCRIPTION: Validate Markdown documentation image paths and asset locations
# USAGE: ./scripts/check_doc_assets.py
# PARAMETERS:
#   None
# EXAMPLE: ./scripts/check_doc_assets.py
# ----------------------------------------------------
"""Validate documentation image paths and MkDocs HTML image restrictions."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MARKDOWN_IMAGE = re.compile(r"!\[[^]]*\]\(([^)\s]+)")
HTML_IMAGE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)


def image_paths(text: str) -> list[tuple[str, str]]:
    return [("markdown", path) for path in MARKDOWN_IMAGE.findall(text)] + [
        ("html", path) for path in HTML_IMAGE.findall(text)
    ]


def expected_asset_prefix(source: Path) -> str:
    if source == ROOT / "README.md":
        return "docs/assets/"
    return "assets/"


def main() -> int:
    if sys.argv[1:] in (["-h"], ["--help"]):
        print("Usage: ./scripts/check_doc_assets.py\n\nValidate Markdown documentation image paths and asset locations.")
        return 0
    if len(sys.argv) != 1:
        print("usage: ./scripts/check_doc_assets.py", file=sys.stderr)
        return 2
    errors: list[str] = []
    sources = [ROOT / "README.md", *sorted(DOCS.rglob("*.md"))]
    for source in sources:
        prefix = expected_asset_prefix(source)
        for kind, target in image_paths(source.read_text()):
            if target.startswith(("http://", "https://", "data:")):
                continue
            if kind == "html" and source not in {ROOT / "README.md", DOCS / "index.md"}:
                errors.append(
                    f"{source.relative_to(ROOT)}: use Markdown image syntax outside the home page: {target}"
                )
                continue
            if not target.startswith(prefix):
                errors.append(
                    f"{source.relative_to(ROOT)}: use {prefix} for an image asset: {target}"
                )
                continue
            expected = DOCS / "assets" / target.removeprefix(prefix)
            if not expected.is_file():
                errors.append(f"{source.relative_to(ROOT)}: missing image: {target}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Documentation image paths are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
