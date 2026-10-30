# Pixel Art JSON Format

Pixel Art JSON stores high-level drawing intent instead of a final pixel matrix. It is meant to be short enough for AI output and clear enough for manual editing.

## Document Structure

```json
{
  "version": "0.1",
  "metadata": { "title": "optional" },
  "canvas": { "width": 24, "height": 24, "background": null },
  "palette": { "outline": "#1b1b1b", "body": "#55c96f" },
  "components": {},
  "layers": [
    { "name": "sprite", "visible": true, "opacity": 1, "operations": [] }
  ]
}
```

Use integer pixel coordinates. The origin is the top-left pixel. Rectangles use `x`, `y`, `w`, and `h`, where `w` and `h` are pixel counts.

The renderer accepts canvases up to 4,194,304 pixels. When scaling, the final image is limited to 16,777,216 pixels. Coordinates must fit in the signed 32-bit range. These limits are checked before image allocation so malformed or accidental sizes fail with a readable error instead of exhausting memory. Palette references and component stamps may nest up to 64 levels; cycles are rejected.

Documents must be strict JSON objects. Duplicate object keys and non-standard numeric constants such as `NaN` and `Infinity` are rejected.

## Colors

Colors can be:

- A palette key: `"outline"`
- A hex color: `"#55c96f"` or `"#55c96fff"`
- A Pillow/CSS color name: `"white"`
- An RGB/RGBA array: `[85, 201, 111, 255]`
- `null` or `"transparent"` for transparent pixels

Prefer palette keys in operations. It makes global color edits cheap.

## Layers

`layers` is optional but recommended. Each layer contains operations and may set:

- `name`: Human-readable label
- `visible`: Set to `false` to skip rendering
- `opacity`: Number from `0` to `1`

If `layers` is missing, top-level `operations` is rendered.

## Components And Stamps

Components are reusable operation lists. Use them for repeated eyes, wheels, buttons, sparkles, icons, and other repeated shapes.

```json
{
  "components": {
    "eye": [
      { "op": "rect", "color": "outline", "x": 0, "y": 0, "w": 4, "h": 3 },
      { "op": "rect", "color": "white", "x": 1, "y": 1, "w": 2, "h": 1 }
    ]
  },
  "layers": [
    {
      "name": "face",
      "operations": [
        { "op": "stamp", "component": "eye", "x": 6, "y": 8 },
        { "op": "stamp", "component": "eye", "x": 14, "y": 8 }
      ]
    }
  ]
}
```

Component coordinates are relative to the stamp location. Components may also be objects with an `anchor` point and `operations`.

## Operations

### `rect`

Filled rectangle.

```json
{ "op": "rect", "color": "body", "x": 4, "y": 6, "w": 12, "h": 8 }
```

### `outline_rect`

Rectangle outline. Optional `width` defaults to `1`.

```json
{ "op": "outline_rect", "color": "outline", "x": 4, "y": 6, "w": 12, "h": 8 }
```

### `ellipse`

Filled ellipse inside a bounding box. Optional `outline` adds an outline color.

```json
{ "op": "ellipse", "color": "body", "outline": "outline", "x": 4, "y": 5, "w": 14, "h": 10 }
```

### `line`

Pixel line. Optional `width` defaults to `1`.

```json
{ "op": "line", "color": "outline", "x1": 2, "y1": 2, "x2": 10, "y2": 7 }
```

### `path`

Connected line segments.

```json
{ "op": "path", "color": "outline", "points": [[2, 2], [4, 4], [7, 4]] }
```

### `polygon`

Filled polygon.

```json
{ "op": "polygon", "color": "body", "points": [[8, 2], [14, 8], [3, 8]] }
```

### `pixels`

Small local pixel clusters. Keep this short; do not use it as a full sprite matrix.

```json
{ "op": "pixels", "color": "shine", "points": [[6, 6], [7, 6], [6, 7]] }
```

Individual points may override the operation color with a three-item `[x, y, color]` tuple:

```json
{ "op": "pixels", "points": [[6, 6, "red"], [7, 6, "#ffffff"]] }
```

### `erase`

Clear pixels to transparent. Use either `x`, `y`, `w`, `h` or `points`.

```json
{ "op": "erase", "x": 0, "y": 0, "w": 4, "h": 4 }
```

### `stamp`

Draw a component at `x`, `y`.

```json
{ "op": "stamp", "component": "eye", "x": 10, "y": 13 }
```

## AI Authoring Guidelines

- Use canvas sizes like `16`, `24`, `32`, `48`, or `64`.
- Use names in the palette, not inline colors everywhere.
- Prefer rectangles, lines, ellipses, polygons, and stamps.
- Use `pixels` only for details such as highlights, eyes, mouth corners, texture, and cleanup.
- Avoid emitting a full grid of every pixel.
- For edits, preserve the existing document and change only the relevant palette entries or operations.

