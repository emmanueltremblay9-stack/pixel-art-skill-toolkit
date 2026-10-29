from __future__ import annotations

import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from pixel_art_skill_toolkit.cli import main, render_main
from pixel_art_skill_toolkit.format import parse_json, save_document
from pixel_art_skill_toolkit.renderer import (
    MAX_CANVAS_PIXELS,
    MAX_OUTPUT_PIXELS,
    load_document,
    render_document,
    save_png,
)

try:
    from pixel_art_skill_toolkit.gui import JsonDialog, PixelArtEditor
except ModuleNotFoundError as exc:
    if exc.name not in {"tkinter", "_tkinter"}:
        raise
    JsonDialog = None
    PixelArtEditor = None


def make_document(**overrides):
    document = {
        "version": "0.1",
        "canvas": {"width": 4, "height": 4, "background": None},
        "palette": {"red": "#ff0000"},
        "operations": [],
    }
    document.update(overrides)
    return document


class InputSafetyTest(unittest.TestCase):
    def test_rejects_non_object_document(self) -> None:
        with self.assertRaisesRegex(ValueError, "JSON object"):
            render_document([])  # type: ignore[arg-type]

    def test_rejects_canvas_over_pixel_limit_before_render(self) -> None:
        document = make_document(
            canvas={"width": MAX_CANVAS_PIXELS + 1, "height": 1, "background": None}
        )
        with self.assertRaisesRegex(ValueError, "canvas exceeds the maximum pixel count"):
            render_document(document)

    def test_rejects_scaled_output_over_pixel_limit_before_render(self) -> None:
        side = math.isqrt(MAX_CANVAS_PIXELS)
        document = make_document(canvas={"width": side, "height": side, "background": None})
        with self.assertRaisesRegex(ValueError, "scaled image exceeds the maximum pixel count"):
            render_document(document, scale=math.isqrt(MAX_OUTPUT_PIXELS) // side + 1)

    def test_rejects_boolean_dimensions(self) -> None:
        document = make_document(canvas={"width": True, "height": 1, "background": None})
        with self.assertRaisesRegex(ValueError, "canvas.width must be an integer"):
            render_document(document)

    def test_rejects_non_boolean_visibility(self) -> None:
        document = make_document(
            layers=[{"name": "bad", "visible": "false", "operations": []}]
        )
        with self.assertRaisesRegex(ValueError, r"layers\[0\].visible must be a boolean"):
            render_document(document)

    def test_rejects_non_finite_opacity(self) -> None:
        document = make_document(
            layers=[{"name": "bad", "opacity": float("nan"), "operations": []}]
        )
        with self.assertRaisesRegex(ValueError, "opacity must be a finite number"):
            render_document(document)

    def test_all_examples_render(self) -> None:
        examples_dir = Path(__file__).resolve().parents[1] / "examples"
        for path in sorted(examples_dir.glob("*.json")):
            with self.subTest(example=path.name):
                self.assertGreater(render_document(load_document(path)).width, 0)

    def test_block_breaker_v2_has_separated_vanilla_player_inventory(self) -> None:
        sample_path = Path(__file__).resolve().parents[1] / "examples" / "block-breaker-gui-v2.json"
        document = load_document(sample_path)
        self.assertEqual(document["canvas"]["height"], 172)
        operations = document["layers"][0]["operations"]
        slots = [
            operation for operation in operations
            if operation.get("op") == "stamp" and operation.get("component") == "inventory_slot"
        ]
        self.assertEqual(len(slots), 36)
        self.assertEqual(sorted({slot["y"] for slot in slots}), [91, 109, 127, 150])
        expected_x = [7 + 18 * column for column in range(9)]
        for row_y in (91, 109, 127, 150):
            self.assertEqual(sorted(slot["x"] for slot in slots if slot["y"] == row_y), expected_x)

    def test_palette_cycles_raise_clear_value_error(self) -> None:
        document = make_document(
            palette={"first": "second", "second": "first"},
            operations=[{"op": "rect", "color": "first", "x": 0, "y": 0, "w": 1, "h": 1}],
        )
        with self.assertRaisesRegex(ValueError, "palette color reference cycle"):
            render_document(document)

    def test_component_cycles_raise_clear_value_error(self) -> None:
        document = make_document(
            components={"loop": [{"op": "stamp", "component": "loop", "x": 0, "y": 0}]},
            operations=[{"op": "stamp", "component": "loop", "x": 0, "y": 0}],
        )
        with self.assertRaisesRegex(ValueError, "recursive component stamp"):
            render_document(document)

    def test_rejects_points_with_extra_coordinates(self) -> None:
        document = make_document(
            operations=[
                {"op": "path", "color": "red", "points": [[0, 0, 1], [1, 1]]}
            ]
        )
        with self.assertRaisesRegex(ValueError, r"must be a point array \[x, y\]"):
            render_document(document)

    def test_rejects_non_array_path_and_polygon_points(self) -> None:
        for operation_name in ("path", "polygon"):
            for points in (None, 7):
                with self.subTest(operation=operation_name, points=points):
                    document = make_document(
                        operations=[
                            {"op": operation_name, "color": "red", "points": points}
                        ]
                    )
                    with self.assertRaisesRegex(ValueError, r"operations\[0\]\.points must be an array"):
                        render_document(document)

    def test_rejects_coordinate_overflow_after_stamp_offsets(self) -> None:
        limit = 2_147_483_647
        document = make_document(
            components={"dot": {"anchor": [-limit, 0], "operations": []}},
            operations=[{"op": "stamp", "component": "dot", "x": limit, "y": 0}],
        )
        with self.assertRaisesRegex(ValueError, "must be between -2147483647 and 2147483647"):
            render_document(document)

    def test_strict_json_rejects_duplicate_keys_and_non_standard_constants(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            parse_json('{"canvas": {}, "canvas": {}}')
        with self.assertRaisesRegex(ValueError, "Non-standard JSON constant"):
            parse_json('{"opacity": NaN}')


class CliAndRoundTripTest(unittest.TestCase):
    def test_cli_invalid_file_has_clean_error_and_status_two(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            bad_file = Path(temp_dir) / "bad.json"
            bad_file.write_text("{", encoding="utf-8")
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as exit_info:
                main(["validate", str(bad_file)])
        self.assertEqual(exit_info.exception.code, 2)
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertIn("Invalid JSON", stderr.getvalue())

    def test_cli_invalid_path_points_has_clean_error_and_status_two(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            bad_file = Path(temp_dir) / "bad-points.json"
            save_document(
                make_document(
                    operations=[{"op": "path", "color": "red", "points": None}]
                ),
                bad_file,
            )
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as exit_info:
                main(["validate", str(bad_file)])
        self.assertEqual(exit_info.exception.code, 2)
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertIn("operations[0].points must be an array", stderr.getvalue())

    def test_cli_missing_file_has_clean_error_and_status_two(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as exit_info:
            main(["validate", "missing-pixel-art-document.json"])
        self.assertEqual(exit_info.exception.code, 2)
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertIn("missing-pixel-art-document.json", stderr.getvalue())

    def test_render_cli_rejects_invalid_scale_without_traceback(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "sprite.json"
            output_path = Path(temp_dir) / "sprite.png"
            save_document(make_document(), input_path)
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as exit_info:
                render_main([str(input_path), "-o", str(output_path), "--scale", "0"])
        self.assertEqual(exit_info.exception.code, 2)
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertIn("scale must be greater than 0", stderr.getvalue())

    def test_json_and_png_import_export_round_trip(self) -> None:
        original = make_document(
            operations=[{"op": "rect", "color": "red", "x": 1, "y": 1, "w": 2, "h": 2}]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "sprite.json"
            png_path = Path(temp_dir) / "sprite.png"
            save_document(original, json_path)
            loaded = load_document(json_path)
            self.assertEqual(loaded, original)
            save_png(loaded, png_path, scale=3)
            with Image.open(png_path) as exported:
                self.assertEqual(exported.format, "PNG")
                self.assertEqual(exported.mode, "RGBA")
                self.assertEqual(exported.size, (12, 12))
                self.assertEqual(exported.getpixel((3, 3)), (255, 0, 0, 255))

    @unittest.skipIf(JsonDialog is None, "Tkinter is unavailable in this Python runtime")
    def test_gui_import_save_and_png_export_flow(self) -> None:
        document = make_document(
            operations=[{"op": "rect", "color": "red", "x": 1, "y": 1, "w": 2, "h": 2}]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.json"
            saved_path = Path(temp_dir) / "saved.json"
            exported_path = Path(temp_dir) / "gui-export.png"
            save_document(document, source_path)

            editor = object.__new__(PixelArtEditor)
            editor.root = Mock()
            editor.document = make_document()
            editor.current_path = None
            editor.set_document = Mock(
                side_effect=lambda new_document: setattr(editor, "document", new_document)
            )
            editor.open_path(source_path)
            self.assertEqual(editor.document, document)
            self.assertEqual(editor.current_path, source_path)
            editor.set_document.assert_called_once_with(document)

            editor.current_path = saved_path
            editor.apply_json = Mock(return_value=True)
            editor.preview_scale = Mock()
            editor.preview_scale.get.return_value = 3
            editor.save_file()
            self.assertEqual(load_document(saved_path), document)

            with patch(
                "pixel_art_skill_toolkit.gui.filedialog.asksaveasfilename",
                return_value=str(exported_path),
            ):
                editor.export_png()
            with Image.open(exported_path) as exported:
                self.assertEqual(exported.size, (12, 12))
                self.assertEqual(exported.getpixel((3, 3)), (255, 0, 0, 255))

    def test_failed_atomic_json_save_preserves_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "sprite.json"
            destination.write_text("keep this file", encoding="utf-8")
            with patch("pixel_art_skill_toolkit.format.os.replace", side_effect=OSError("blocked")):
                with self.assertRaisesRegex(OSError, "blocked"):
                    save_document(make_document(), destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "keep this file")
            self.assertEqual(list(Path(temp_dir).glob(".sprite.json.*.tmp")), [])

    def test_failed_atomic_png_save_preserves_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "sprite.png"
            destination.write_bytes(b"keep this file")
            with patch("pixel_art_skill_toolkit.renderer.os.replace", side_effect=OSError("blocked")):
                with self.assertRaisesRegex(OSError, "blocked"):
                    save_png(make_document(), destination)
            self.assertEqual(destination.read_bytes(), b"keep this file")
            self.assertEqual(list(Path(temp_dir).glob(".sprite.*.png")), [])

    def test_repeated_rendering_is_deterministic(self) -> None:
        document = make_document(
            layers=[
                {"name": "base", "opacity": 1.0, "operations": [{"op": "rect", "color": "red", "x": 1, "y": 1, "w": 2, "h": 2}]}
            ]
        )
        expected = render_document(document, scale=4).tobytes()
        for _ in range(50):
            self.assertEqual(render_document(document, scale=4).tobytes(), expected)

    @unittest.skipIf(JsonDialog is None, "Tkinter is unavailable in this Python runtime")
    def test_gui_operation_dialog_rejects_non_object_json(self) -> None:
        dialog = object.__new__(JsonDialog)
        dialog.text = Mock()
        dialog.text.get.return_value = "[]"
        dialog.result = None
        with patch("pixel_art_skill_toolkit.gui.messagebox.showerror") as show_error:
            self.assertFalse(dialog.validate())
        self.assertIsNone(dialog.result)
        show_error.assert_called_once()

    @unittest.skipIf(JsonDialog is None, "Tkinter is unavailable in this Python runtime")
    def test_gui_keeps_last_document_when_candidate_is_invalid(self) -> None:
        editor = object.__new__(PixelArtEditor)
        editor.root = Mock()
        editor.set_document = Mock()
        with patch(
            "pixel_art_skill_toolkit.gui.render_document",
            side_effect=ValueError("invalid candidate"),
        ), patch("pixel_art_skill_toolkit.gui.messagebox.showerror") as show_error:
            self.assertFalse(editor._set_document_if_valid(make_document()))
        editor.set_document.assert_not_called()
        show_error.assert_called_once()

    @unittest.skipIf(PixelArtEditor is None, "Tkinter is unavailable in this Python runtime")
    def test_gui_invalid_open_keeps_last_document_and_path(self) -> None:
        previous_document = make_document()
        previous_path = Path("previous.json")
        editor = object.__new__(PixelArtEditor)
        editor.root = Mock()
        editor.document = previous_document
        editor.current_path = previous_path
        editor.set_document = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "invalid-canvas.json"
            save_document(
                make_document(canvas={"width": True, "height": 4, "background": None}),
                invalid_path,
            )
            with patch("pixel_art_skill_toolkit.gui.messagebox.showerror") as show_error:
                editor.open_path(invalid_path)

        self.assertIs(editor.document, previous_document)
        self.assertEqual(editor.current_path, previous_path)
        editor.set_document.assert_not_called()
        show_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
