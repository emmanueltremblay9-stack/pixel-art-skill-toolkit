from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw

from .format import parse_json


JsonDict = dict[str, Any]
Point = tuple[int, int]
Color = tuple[int, int, int, int]
MAX_CANVAS_PIXELS = 4_194_304
MAX_OUTPUT_PIXELS = 16_777_216
MAX_COMPONENT_DEPTH = 64
MAX_COLOR_REFERENCE_DEPTH = 64
MAX_COORDINATE_ABS = 2_147_483_647


@dataclass(frozen=True)
class RenderContext:
    palette: dict[str, Any]
    components: dict[str, Any]


def load_document(path: str | Path) -> JsonDict:
    document = parse_json(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Pixel art document must be a JSON object.")
    return document


def save_png(document: JsonDict, output_path: str | Path, scale: int | None = None) -> None:
    image = render_document(document, scale=scale)
    destination = Path(output_path)
    temporary_path: str | None = None
    try:
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{destination.stem}.",
            suffix=".png",
            dir=destination.parent,
        )
        os.close(descriptor)
        image.save(temporary_path, format="PNG")
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
        raise


def render_document(document: JsonDict, scale: int | None = None) -> Image.Image:
    if not isinstance(document, dict):
        raise ValueError("Pixel art document must be a JSON object.")

    canvas = _required_object(document, "canvas")
    palette = _required_object(document, "palette")
    width = _positive_int(canvas.get("width"), "canvas.width")
    height = _positive_int(canvas.get("height"), "canvas.height")
    canvas_pixels = width * height
    if canvas_pixels > MAX_CANVAS_PIXELS:
        raise ValueError(
            f"canvas exceeds the maximum pixel count of {MAX_CANVAS_PIXELS:,}."
        )

    scale_value: int | None = None
    if scale is not None:
        scale_value = _positive_int(scale, "scale")
        output_pixels = canvas_pixels * scale_value * scale_value
        if output_pixels > MAX_OUTPUT_PIXELS:
            raise ValueError(
                f"scaled image exceeds the maximum pixel count of {MAX_OUTPUT_PIXELS:,}."
            )

    components = document.get("components", {})
    if not isinstance(components, dict):
        raise ValueError("components must be an object.")

    background = _resolve_color(canvas.get("background"), palette)

    image = Image.new("RGBA", (width, height), background)
    context = RenderContext(
        palette=palette,
        components=components,
    )

    layers = document.get("layers")
    if layers is None:
        _render_operations(image, document.get("operations", []), context)
    else:
        if not isinstance(layers, list):
            raise ValueError("layers must be an array.")
        for layer_index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                raise ValueError(f"layers[{layer_index}] must be an object.")
            visible = layer.get("visible", True)
            if not isinstance(visible, bool):
                raise ValueError(f"layers[{layer_index}].visible must be a boolean.")
            if not visible:
                continue
            opacity = _opacity(layer.get("opacity", 1.0), f"layers[{layer_index}].opacity")
            layer_image = Image.new("RGBA", image.size, (0, 0, 0, 0))
            _render_operations(
                layer_image,
                layer.get("operations", []),
                context,
                path=f"layers[{layer_index}].operations",
            )
            if opacity < 1.0:
                alpha = layer_image.getchannel("A").point(lambda value: int(value * opacity))
                layer_image.putalpha(alpha)
            image.alpha_composite(layer_image)

    if scale_value is not None:
        if scale_value != 1:
            image = image.resize((width * scale_value, height * scale_value), Image.Resampling.NEAREST)
    return image


def _render_operations(
    image: Image.Image,
    operations: Any,
    context: RenderContext,
    origin: Point = (0, 0),
    path: str = "operations",
    component_stack: tuple[str, ...] = (),
) -> None:
    if not isinstance(operations, list):
        raise ValueError(f"{path} must be an array.")

    draw = ImageDraw.Draw(image)
    for index, operation in enumerate(operations):
        op_path = f"{path}[{index}]"
        if not isinstance(operation, dict):
            raise ValueError(f"{op_path} must be an object.")
        op_name = operation.get("op")
        if not isinstance(op_name, str):
            raise ValueError(f"{op_path}.op must be a string.")

        if op_name == "rect":
            color = _operation_color(operation, context.palette, op_path)
            draw.rectangle(_box(operation, origin, op_path), fill=color)
        elif op_name == "outline_rect":
            color = _operation_color(operation, context.palette, op_path)
            width = _positive_int(operation.get("width", 1), f"{op_path}.width")
            draw.rectangle(_box(operation, origin, op_path), outline=color, width=width)
        elif op_name == "ellipse":
            color = _operation_color(operation, context.palette, op_path)
            outline = _optional_color(operation.get("outline"), context.palette)
            draw.ellipse(_box(operation, origin, op_path), fill=color, outline=outline)
        elif op_name == "line":
            color = _operation_color(operation, context.palette, op_path)
            width = _positive_int(operation.get("width", 1), f"{op_path}.width")
            draw.line(_line_points(operation, origin, op_path), fill=color, width=width)
        elif op_name == "path":
            color = _operation_color(operation, context.palette, op_path)
            width = _positive_int(operation.get("width", 1), f"{op_path}.width")
            points = _points(operation, origin, op_path)
            if len(points) < 2:
                raise ValueError(f"{op_path}.points must contain at least two points.")
            draw.line(points, fill=color, width=width)
        elif op_name == "polygon":
            color = _operation_color(operation, context.palette, op_path)
            points = _points(operation, origin, op_path)
            if len(points) < 3:
                raise ValueError(f"{op_path}.points must contain at least three points.")
            draw.polygon(points, fill=color)
        elif op_name == "pixels":
            default_color = operation.get("color")
            points = operation.get("points", [])
            if not isinstance(points, list):
                raise ValueError(f"{op_path}.points must be an array.")
            for point_index, point_value in enumerate(points):
                point_path = f"{op_path}.points[{point_index}]"
                point_color = default_color
                if isinstance(point_value, list) and len(point_value) == 3:
                    point_color = point_value[2]
                    point_value = point_value[:2]
                color = _resolve_color(point_color, context.palette)
                draw.point(_point(point_value, origin, point_path), fill=color)
        elif op_name == "erase":
            _erase(image, draw, operation, origin, op_path)
        elif op_name == "stamp":
            _stamp(image, operation, context, origin, op_path, component_stack)
        else:
            raise ValueError(f"Unsupported operation {op_name!r} at {op_path}.")


def _stamp(
    image: Image.Image,
    operation: JsonDict,
    context: RenderContext,
    origin: Point,
    path: str,
    component_stack: tuple[str, ...],
) -> None:
    component_name = operation.get("component")
    if not isinstance(component_name, str):
        raise ValueError(f"{path}.component must be a string.")
    if component_name not in context.components:
        raise ValueError(f"{path}.component references unknown component {component_name!r}.")
    if component_name in component_stack:
        cycle = " -> ".join((*component_stack, component_name))
        raise ValueError(f"recursive component stamp detected: {cycle}.")
    if len(component_stack) >= MAX_COMPONENT_DEPTH:
        raise ValueError(f"component stamp nesting exceeds {MAX_COMPONENT_DEPTH} levels.")

    component = context.components[component_name]
    if isinstance(component, list):
        component_operations = component
        anchor = (0, 0)
    elif isinstance(component, dict):
        component_operations = component.get("operations", [])
        anchor = _point(component.get("anchor", [0, 0]), (0, 0), f"components.{component_name}.anchor")
    else:
        raise ValueError(f"components.{component_name} must be an object or operation array.")

    x = _int(operation.get("x", 0), f"{path}.x")
    y = _int(operation.get("y", 0), f"{path}.y")
    stamp_origin = (
        _offset(origin[0], x - anchor[0], f"{path}.x"),
        _offset(origin[1], y - anchor[1], f"{path}.y"),
    )
    _render_operations(
        image,
        component_operations,
        context,
        origin=stamp_origin,
        path=f"components.{component_name}.operations",
        component_stack=(*component_stack, component_name),
    )


def _erase(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    operation: JsonDict,
    origin: Point,
    path: str,
) -> None:
    if "points" in operation:
        points = operation["points"]
        if not isinstance(points, list):
            raise ValueError(f"{path}.points must be an array.")
        for index, point_value in enumerate(points):
            draw.point(_point(point_value, origin, f"{path}.points[{index}]"), fill=(0, 0, 0, 0))
        return
    draw.rectangle(_box(operation, origin, path), fill=(0, 0, 0, 0))


def _required_object(document: JsonDict, key: str) -> JsonDict:
    value = document.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object.")
    return value


def _resolve_color(
    value: Any,
    palette: dict[str, Any],
    resolving: tuple[str, ...] = (),
) -> Color:
    if value is None or value == "transparent":
        return (0, 0, 0, 0)
    if isinstance(value, str) and value in palette:
        if value in resolving:
            cycle = " -> ".join((*resolving, value))
            raise ValueError(f"palette color reference cycle detected: {cycle}.")
        if len(resolving) >= MAX_COLOR_REFERENCE_DEPTH:
            raise ValueError(
                f"palette color reference chain exceeds {MAX_COLOR_REFERENCE_DEPTH} levels."
            )
        return _resolve_color(palette[value], palette, (*resolving, value))
    if isinstance(value, str):
        try:
            return ImageColor.getcolor(value, "RGBA")
        except ValueError as exc:
            raise ValueError(f"Invalid color value: {value!r}.") from exc
    if isinstance(value, list) and len(value) in (3, 4):
        channels = [_channel(channel) for channel in value]
        if len(channels) == 3:
            channels.append(255)
        return tuple(channels)  # type: ignore[return-value]
    raise ValueError(f"Invalid color value: {value!r}.")


def _optional_color(value: Any, palette: dict[str, Any]) -> Color | None:
    if value is None:
        return None
    return _resolve_color(value, palette)


def _operation_color(operation: JsonDict, palette: dict[str, Any], path: str) -> Color:
    if "color" not in operation:
        raise ValueError(f"{path}.color is required.")
    return _resolve_color(operation["color"], palette)


def _box(operation: JsonDict, origin: Point, path: str) -> tuple[int, int, int, int]:
    x = _offset(origin[0], _int(operation.get("x"), f"{path}.x"), f"{path}.x")
    y = _offset(origin[1], _int(operation.get("y"), f"{path}.y"), f"{path}.y")
    width = _positive_int(operation.get("w"), f"{path}.w")
    height = _positive_int(operation.get("h"), f"{path}.h")
    return (
        x,
        y,
        _offset(x, width - 1, f"{path}.w end"),
        _offset(y, height - 1, f"{path}.h end"),
    )


def _line_points(operation: JsonDict, origin: Point, path: str) -> tuple[int, int, int, int]:
    return (
        _offset(origin[0], _int(operation.get("x1"), f"{path}.x1"), f"{path}.x1"),
        _offset(origin[1], _int(operation.get("y1"), f"{path}.y1"), f"{path}.y1"),
        _offset(origin[0], _int(operation.get("x2"), f"{path}.x2"), f"{path}.x2"),
        _offset(origin[1], _int(operation.get("y2"), f"{path}.y2"), f"{path}.y2"),
    )


def _point(value: Any, origin: Point, path: str) -> Point:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ValueError(f"{path} must be a point array [x, y].")
    return (
        _offset(origin[0], _int(value[0], f"{path}[0]"), f"{path}[0]"),
        _offset(origin[1], _int(value[1], f"{path}[1]"), f"{path}[1]"),
    )


def _points(operation: JsonDict, origin: Point, path: str) -> list[Point]:
    values = operation.get("points", [])
    if not isinstance(values, list):
        raise ValueError(f"{path}.points must be an array.")
    return [
        _point(value, origin, f"{path}.points[{index}]")
        for index, value in enumerate(values)
    ]


def _int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path} must be an integer.")
    return _coordinate(value, path)


def _coordinate(value: int, path: str) -> int:
    if value < -MAX_COORDINATE_ABS or value > MAX_COORDINATE_ABS:
        raise ValueError(f"{path} must be between {-MAX_COORDINATE_ABS} and {MAX_COORDINATE_ABS}.")
    return value


def _offset(origin: int, offset: int, path: str) -> int:
    return _coordinate(origin + offset, path)


def _positive_int(value: Any, path: str) -> int:
    number = _int(value, path)
    if number <= 0:
        raise ValueError(f"{path} must be greater than 0.")
    return number


def _opacity(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{path} must be a finite number.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} must be a finite number.")
    if value < 0 or value > 1:
        raise ValueError(f"{path} must be between 0 and 1.")
    return float(value)


def _channel(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 255:
        raise ValueError(f"Color channels must be integers from 0 to 255: {value!r}.")
    return value

