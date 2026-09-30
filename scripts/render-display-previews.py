#!/usr/bin/env python3
# SCRIPT: render-display-previews
# DESCRIPTION: Render deterministic V2 display previews from source SVG icons
# USAGE: ./scripts/render-display-previews.py [--output-dir DIRECTORY] [--write-header|--check]
# PARAMETERS:
#   --output-dir DIRECTORY  Directory for generated preview PNG files
#   --write-header           Update the generated firmware icon header
#   --check                  Fail when the generated firmware icon header is stale
# EXAMPLE: ./scripts/render-display-previews.py --check
# ----------------------------------------------------
"""Render deterministic V2 state-screen previews without a connected board."""

import argparse
import re
import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "firmware/assets/icons"
HEADER = ROOT / "firmware/main/include/state_icons.generated.h"


class Canvas:
    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        self.pixels = bytearray([255]) * (width * height)

    def rect(self, x: int, y: int, width: int, height: int) -> None:
        for row in range(y, y + height):
            for column in range(x, x + width):
                if 0 <= column < self.width and 0 <= row < self.height:
                    self.pixels[row * self.width + column] = 0

    def line(self, x0: int, y0: int, x1: int, y1: int, width: int = 2) -> None:
        dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
        dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            self.rect(x0 - width // 2, y0 - width // 2, width, width)
            if x0 == x1 and y0 == y1:
                return
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += sx
            if doubled <= dx:
                error += dx
                y0 += sy

    def circle(self, center_x: int, center_y: int, radius: int, width: int = 2) -> None:
        x, y, error = radius, 0, 1 - radius
        while x >= y:
            for point_x, point_y in ((center_x + x, center_y + y), (center_x + y, center_y + x),
                                     (center_x - y, center_y + x), (center_x - x, center_y + y),
                                     (center_x - x, center_y - y), (center_x - y, center_y - x),
                                     (center_x + y, center_y - x), (center_x + x, center_y - y)):
                self.rect(point_x - width // 2, point_y - width // 2, width, width)
            y += 1
            if error < 0:
                error += 2 * y + 1
            else:
                x -= 1
                error += 2 * (y - x + 1)

    def png(self, path: Path) -> None:
        raw = b"".join(b"\0" + bytes(self.pixels[row * self.width:(row + 1) * self.width]) for row in range(self.height))
        def chunk(kind: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def command_values(command):
    if command["kind"] == "line": return command["x1"], command["y1"], command["x2"], command["y2"], command["width"]
    if command["kind"] == "circle": return command["x"], command["y"], command["radius"], 0, command["width"]
    return command["x"], command["y"], command["width"], command["height"], command.get("stroke", 0)


def render(commands) -> Canvas:
    canvas = Canvas(200, 200)
    border = 8
    canvas.rect(border, border, canvas.width - 2 * border, border)
    canvas.rect(border, canvas.height - 2 * border, canvas.width - 2 * border, border)
    canvas.rect(border, border, border, canvas.height - 2 * border)
    canvas.rect(canvas.width - 2 * border, border, border, canvas.height - 2 * border)
    for command in commands:
        a, b, c, d, width = command_values(command)
        if command["kind"] == "line": canvas.line(a, b, c, d, width)
        elif command["kind"] == "circle": canvas.circle(a, b, c, width)
        elif command["kind"] == "stroke_rect":
            canvas.line(a, b, a + c, b, width); canvas.line(a + c, b, a + c, b + d, width)
            canvas.line(a + c, b + d, a, b + d, width); canvas.line(a, b + d, a, b, width)
        else: canvas.rect(a, b, c, d)
    return canvas


def generated_header(icons) -> str:
    rows = ["#pragma once", "", "#include <array>", "#include <cstddef>", "#include <cstdint>", "", "namespace inkmate::assets {", "", "enum class IconPrimitive : std::uint8_t { Line, Circle, Rect, Box };", "struct IconCommand { IconPrimitive primitive; int16_t a; int16_t b; int16_t c; int16_t d; int16_t width; };", ""]
    for name, commands in icons.items():
        rows.append(f"inline constexpr std::array<IconCommand, {len(commands)}> k{name.title()}{{{{")
        for command in commands:
            a, b, c, d, width = command_values(command)
            primitive = "Box" if command["kind"] == "stroke_rect" else command["kind"].title()
            rows.append(f"    {{IconPrimitive::{primitive}, {a}, {b}, {c}, {d}, {width}}},")
        rows.extend(["}};", ""])
    return "\n".join(rows + ["}  // namespace inkmate::assets", ""])


def load_icons():
    icons = {}
    for source in sorted(SOURCE.glob("*.svg")):
        commands, start, current = [], None, None
        for element in ET.parse(source).getroot():
            tag = element.tag.rsplit("}", 1)[-1]
            width = int(element.get("stroke-width", "1"))
            if tag == "circle":
                commands.append({"kind": "circle", "x": int(element.get("cx")), "y": int(element.get("cy")), "radius": int(element.get("r")), "width": width})
            elif tag == "rect":
                commands.append({"kind": "stroke_rect", "x": int(element.get("x")), "y": int(element.get("y")), "width": int(element.get("width")), "height": int(element.get("height")), "stroke": width})
            elif tag == "path":
                tokens = re.findall(r"[MLZ]|-?\d+", element.get("d", ""))
                index, start, current = 0, None, None
                while index < len(tokens):
                    token = tokens[index]; index += 1
                    if token == "Z":
                        if start and current and current != start:
                            commands.append({"kind": "line", "x1": current[0], "y1": current[1], "x2": start[0], "y2": start[1], "width": width})
                        continue
                    if token not in {"M", "L"}:
                        raise ValueError(f"unsupported SVG command in {source}")
                    point = (int(tokens[index]), int(tokens[index + 1])); index += 2
                    if token == "M": start = point
                    elif current: commands.append({"kind": "line", "x1": current[0], "y1": current[1], "x2": point[0], "y2": point[1], "width": width})
                    current = point
            else:
                raise ValueError(f"unsupported SVG element {tag} in {source}")
        icons[source.stem] = commands
    return icons


def main() -> None:
    parser = argparse.ArgumentParser(description="Render V2 e-paper state previews")
    parser.add_argument("--output-dir", default=str(ROOT / "firmware/previews"))
    parser.add_argument("--write-header", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    icons = load_icons()
    header = generated_header(icons)
    if args.check:
        if not HEADER.exists() or HEADER.read_text() != header:
            raise SystemExit("state icon header is stale; run ./dev previews --write-header")
        return
    if args.write_header:
        HEADER.write_text(header)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for state, commands in icons.items():
        path = output / f"{state}.png"
        render(commands).png(path)
        print(path)


if __name__ == "__main__":
    main()
