from __future__ import annotations

import argparse
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def render_svg_to_ico(svg_path: Path, ico_path: Path, size: int = 256) -> None:
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG: {svg_path}")

    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    ico_path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(ico_path), "ICO"):
        raise RuntimeError("Failed to save ICO output")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Windows ICO icon from an SVG file.")
    parser.add_argument("--svg", type=Path, required=True, help="Input SVG path")
    parser.add_argument("--ico", type=Path, required=True, help="Output ICO path")
    parser.add_argument("--size", type=int, default=256, help="Icon size in pixels")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = QGuiApplication([])
    try:
        render_svg_to_ico(args.svg, args.ico, args.size)
        return 0
    finally:
        app.quit()


if __name__ == "__main__":
    raise SystemExit(main())

