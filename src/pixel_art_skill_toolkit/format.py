from __future__ import annotations

import json
from copy import deepcopy
import os
import tempfile
from pathlib import Path
from typing import Any


def default_document() -> dict[str, Any]:
    """Return a small editable starter document."""
    return deepcopy(
        {
            "version": "0.1",
            "canvas": {"width": 16, "height": 16, "background": None},
            "palette": {
                "outline": "#1b1b1b",
                "body": "#69d46f",
                "highlight": "#d7ffd9",
            },
            "layers": [
                {
                    "name": "sprite",
                    "operations": [
                        {
                            "op": "ellipse",
                            "color": "body",
                            "x": 3,
                            "y": 5,
                            "w": 10,
                            "h": 8,
                        },
                        {
                            "op": "outline_rect",
                            "color": "outline",
                            "x": 4,
                            "y": 7,
                            "w": 8,
                            "h": 4,
                        },
                        {
                            "op": "pixels",
                            "color": "highlight",
                            "points": [[6, 6], [7, 6], [6, 7]],
                        },
                    ],
                }
            ],
        }
    )


def pretty_json(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def parse_json(source: str) -> Any:
    """Parse strict JSON and reject duplicate keys and non-standard constants."""

    try:
        return json.loads(
            source,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_standard_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})."
        ) from exc


def save_document(document: dict[str, Any], path: str | Path) -> None:
    """Atomically save formatted Pixel Art JSON beside its destination."""

    destination = Path(path)
    text = pretty_json(document)
    temporary_path: str | None = None
    try:
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
        raise


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key {key!r}.")
        result[key] = value
    return result


def _reject_non_standard_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON constant {value!r} is not allowed.")

