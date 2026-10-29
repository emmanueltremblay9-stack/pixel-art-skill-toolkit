# Pixel Art Skill Toolkit

**Language:** English | [简体中文](docs/readme.zh-CN.md) | [日本語](docs/readme.ja.md) | [Español](docs/readme.es.md) | [Français](docs/readme.fr.md) | [Deutsch](docs/readme.de.md)

Pixel Art Skill Toolkit is an open-source toolkit for AI-assisted pixel art. It defines a compact, human-editable JSON format, renders that JSON to PNG, and includes a lightweight desktop editor for reviewing and modifying AI-generated pixel art source files.

The core idea: AI should not output a full pixel matrix, Base64 image, or long ASCII sprite. Instead, it should output concise drawing instructions such as palettes, layers, operations, and reusable stamps. The toolkit turns those instructions into real pixel-art PNG files.

## Features

- Portable AI skill: `skill/pixel-art-json/SKILL.md`
- Compact Pixel Art JSON format
- JSON-to-PNG renderer with transparent background support
- Integer scaling with nearest-neighbor pixels
- Tkinter GUI editor for JSON, palette, operations, preview, save, and PNG export
- Example sprites and format documentation
- JSON Schema for editor and tooling integration

## Install

```bash
git clone https://github.com/emmanueltremblay9-stack/pixel-art-skill-toolkit.git
cd pixel-art-skill-toolkit
python -m pip install -e .
```

Requires Python 3.10+ and Pillow. Tkinter is included with most desktop Python installations.

## Render A Sprite

```bash
pixel-art-render examples/slime.json -o slime.png --scale 12
```

## Block Breaker GUI Prototype

This original, illustrative machine screen is generated from [`examples/block-breaker-gui.json`](examples/block-breaker-gui.json). The PNG below is rendered from that JSON at 4× scale. It shows a target block, break progress, a placeholder drop tile, a redstone enable control, a rear-output marker, and a 7×46 logical energy meter with a bottom-input marker. These are proposals: machine behavior, FE cost, exact GUI size, control semantics, and output-slot count remain undecided.

![Block Breaker machine GUI prototype](examples/block-breaker-gui.png)

The separate [`examples/inventory-panel.json`](examples/inventory-panel.json) demonstrates a Minecraft-style panel composition.

For local source-tree development before installing:

```bash
PYTHONPATH=src python -m pixel_art_skill_toolkit render examples/slime.json -o slime.png --scale 12
```

PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m pixel_art_skill_toolkit render examples\slime.json -o slime.png --scale 12
```

## Open The GUI Editor

Double-click on Windows:

```text
launch_gui.bat
```

PowerShell:

```powershell
.\launch_gui.ps1
```

After installing the package:

```bash
pixel-art-gui
```

Or open a file directly:

```bash
pixel-art-toolkit gui examples/slime.json
```

The editor can open a Pixel Art JSON file, render a preview, edit raw JSON, edit palette colors, add/edit/delete drawing operations, save JSON, and export PNG.

The preview panel uses scrollbars, so large integer-scaled sprites remain reachable instead of being clipped by the window edge.

## Format Overview

A minimal file looks like this:

```json
{
  "version": "0.1",
  "canvas": { "width": 16, "height": 16, "background": null },
  "palette": {
    "outline": "#1b1b1b",
    "body": "#69d46f",
    "shine": "#d7ffd9"
  },
  "layers": [
    {
      "name": "sprite",
      "operations": [
        { "op": "ellipse", "color": "body", "x": 3, "y": 5, "w": 10, "h": 8 },
        { "op": "outline_rect", "color": "outline", "x": 4, "y": 7, "w": 8, "h": 4 },
        { "op": "pixels", "color": "shine", "points": [[6, 6], [7, 6]] }
      ]
    }
  ]
}
```

See [docs/json-format.md](docs/json-format.md) for the full operation reference.

## Pixel Art Skill

The reusable AI skill is here:

```text
skill/pixel-art-json/SKILL.md
```

Use it when asking an AI agent to create or edit pixel art in a token-efficient way. It instructs the agent to use high-level JSON operations, shared palettes, components, and localized edits instead of verbose pixel-by-pixel output.

## Documentation

- [JSON format](docs/json-format.md)
- [GUI editor](docs/gui.md)
- [Skill usage](docs/skill-usage.md)
- [JSON Schema](schema/pixel-art.schema.json)

## Examples

- `examples/slime.json`
- `examples/tiny-sword.json`
- `examples/robot-head.json`

## Development

Run tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

Validate an example:

```bash
PYTHONPATH=src python -m pixel_art_skill_toolkit validate examples/slime.json
```

## Project Status

This fork is a stability candidate based on upstream commit `2356465dd88f9ff2c62361eb85cce17a8ed61c06`. It remains pre-release while cross-version CI and hands-on GUI checks are completed. The JSON format remains intentionally small and editable.

The renderer rejects recursive palette/component references and caps canvas and scaled output sizes before allocating image buffers. See [docs/json-format.md](docs/json-format.md) for those limits.

## License

MIT
