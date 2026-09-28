#!/usr/bin/env python3
"""Validate documentation image paths as they are served by MkDocs."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MARKDOWN_IMAGE = re.compile(r"!\[[^]]*\]\(([^)\s]+)")
HTML_IMAGE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)


def image_paths(text: str) -> list[str]:
    return MARKDOWN_IMAGE.findall(text) + HTML_IMAGE.findall(text)


def expected_asset_prefix(source: Path) -> str:
    if source == ROOT / "README.md":
        return "docs/assets/"
    relative = source.relative_to(DOCS)
    depth = len(relative.parts) - (1 if relative.name == "index.md" else 0)
    return "../" * depth + "assets/"


def main() -> int:
    errors: list[str] = []
    sources = [ROOT / "README.md", *sorted(DOCS.rglob("*.md"))]
    for source in sources:
        prefix = expected_asset_prefix(source)
        for target in image_paths(source.read_text()):
            if target.startswith(("http://", "https://", "data:")):
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
