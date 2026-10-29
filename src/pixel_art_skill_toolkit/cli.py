from __future__ import annotations

import argparse
import json
from pathlib import Path

from .renderer import load_document, render_document, save_png


def build_render_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pixel-art-render",
        description="Render compact Pixel Art JSON files to PNG.",
    )
    parser.add_argument("input", type=Path, help="Input Pixel Art JSON file.")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output PNG file.")
    parser.add_argument("--scale", type=int, default=1, help="Integer PNG scale factor.")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pixel-art-toolkit",
        description="Work with compact Pixel Art JSON files.",
    )
    subparsers = parser.add_subparsers(dest="command")

    render_parser = subparsers.add_parser("render", help="Render a Pixel Art JSON file.")
    render_parser.add_argument("input", type=Path, help="Input Pixel Art JSON file.")
    render_parser.add_argument("-o", "--output", type=Path, required=True, help="Output PNG file.")
    render_parser.add_argument("--scale", type=int, default=1, help="Integer PNG scale factor.")

    validate_parser = subparsers.add_parser("validate", help="Parse and render-check a JSON file.")
    validate_parser.add_argument("input", type=Path, help="Input Pixel Art JSON file.")

    gui_parser = subparsers.add_parser("gui", help="Open the GUI editor.")
    gui_parser.add_argument("input", nargs="?", type=Path, help="Optional file to open.")

    return parser


def render_main(argv: list[str] | None = None) -> int:
    parser = build_render_parser()
    args = parser.parse_args(argv)
    try:
        document = load_document(args.input)
        save_png(document, args.output, scale=args.scale)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "render":
            document = load_document(args.input)
            save_png(document, args.output, scale=args.scale)
            return 0

        if args.command == "validate":
            document = load_document(args.input)
            image = render_document(document)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "width": image.width,
                        "height": image.height,
                        "mode": image.mode,
                    },
                    indent=2,
                )
            )
            return 0

        if args.command == "gui":
            from .gui import main as gui_main

            gui_main(args.input)
            return 0
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
