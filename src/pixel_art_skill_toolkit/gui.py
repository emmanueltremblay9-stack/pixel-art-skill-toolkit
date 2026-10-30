from __future__ import annotations

import json
from copy import deepcopy
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from PIL import ImageTk

from .format import default_document, parse_json, pretty_json, save_document
from .renderer import load_document, render_document, save_png


class JsonDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Misc, title: str, initial: Any):
        self.initial = json.dumps(initial, indent=2, ensure_ascii=False)
        self.result: Any = None
        super().__init__(parent, title)

    def body(self, master: tk.Misc) -> tk.Widget:
        self.text = ScrolledText(master, width=54, height=14, wrap="none", undo=True)
        self.text.insert("1.0", self.initial)
        self.text.grid(row=0, column=0, sticky="nsew")
        return self.text

    def validate(self) -> bool:
        try:
            result = parse_json(self.text.get("1.0", "end"))
            if not isinstance(result, dict):
                raise ValueError("An operation must be a JSON object.")
            self.result = result
        except (json.JSONDecodeError, ValueError) as exc:
            messagebox.showerror("Invalid JSON", str(exc), parent=self)
            return False
        return True


class PixelArtEditor:
    def __init__(self, root: tk.Tk, input_path: Path | None = None):
        self.root = root
        self.root.title("Pixel Art Skill Toolkit")
        self.root.geometry("1100x720")
        self.root.minsize(900, 560)
        self.current_path: Path | None = None
        self.document: dict[str, Any] = default_document()
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.preview_item: int | None = None
        self.preview_error_item: int | None = None
        self.preview_scale = tk.IntVar(value=12)

        self._build_menu()
        self._build_layout()
        if input_path:
            self.open_path(input_path)
        else:
            self.set_document(self.document)

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New", command=self.new_document)
        file_menu.add_command(label="Open...", command=self.open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_command(label="Save As...", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Export PNG...", command=self.export_png)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.destroy)
        menu.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menu)

    def _build_layout(self) -> None:
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        json_frame = ttk.Frame(paned, padding=8)
        ttk.Label(json_frame, text="Pixel Art JSON").pack(anchor="w")
        self.json_text = ScrolledText(json_frame, width=58, wrap="none", undo=True)
        self.json_text.pack(fill=tk.BOTH, expand=True, pady=(6, 6))
        json_buttons = ttk.Frame(json_frame)
        json_buttons.pack(fill=tk.X)
        ttk.Button(json_buttons, text="Apply JSON", command=self.apply_json).pack(side=tk.LEFT)
        ttk.Button(json_buttons, text="Format", command=self.format_json).pack(side=tk.LEFT, padx=(6, 0))
        paned.add(json_frame, weight=3)

        right = ttk.Frame(paned, padding=8)
        preview_bar = ttk.Frame(right)
        preview_bar.pack(fill=tk.X)
        ttk.Label(preview_bar, text="Scale").pack(side=tk.LEFT)
        ttk.Spinbox(
            preview_bar,
            from_=1,
            to=64,
            textvariable=self.preview_scale,
            width=5,
            command=self.render_preview,
        ).pack(side=tk.LEFT, padx=(6, 10))
        ttk.Button(preview_bar, text="Render", command=self.render_preview).pack(side=tk.LEFT)

        preview_frame = ttk.Frame(right)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 8))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(preview_frame, highlightthickness=0, background="#f4f4f4")
        preview_xscroll = ttk.Scrollbar(
            preview_frame,
            orient=tk.HORIZONTAL,
            command=self.preview_canvas.xview,
        )
        preview_yscroll = ttk.Scrollbar(
            preview_frame,
            orient=tk.VERTICAL,
            command=self.preview_canvas.yview,
        )
        self.preview_canvas.configure(
            xscrollcommand=preview_xscroll.set,
            yscrollcommand=preview_yscroll.set,
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        preview_yscroll.grid(row=0, column=1, sticky="ns")
        preview_xscroll.grid(row=1, column=0, sticky="ew")
        self.preview_canvas.bind("<Configure>", lambda _event: self._position_preview())

        notebook = ttk.Notebook(right)
        notebook.pack(fill=tk.BOTH, expand=False)
        notebook.add(self._build_palette_tab(notebook), text="Palette")
        notebook.add(self._build_operations_tab(notebook), text="Operations")
        paned.add(right, weight=2)

    def _build_palette_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=6)
        self.palette_tree = ttk.Treeview(frame, columns=("name", "value"), show="headings", height=7)
        self.palette_tree.heading("name", text="Name")
        self.palette_tree.heading("value", text="Color")
        self.palette_tree.column("name", width=120)
        self.palette_tree.column("value", width=140)
        self.palette_tree.pack(fill=tk.BOTH, expand=True)

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(buttons, text="Add", command=self.add_palette_color).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Edit", command=self.edit_palette_color).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(buttons, text="Delete", command=self.delete_palette_color).pack(side=tk.LEFT, padx=(6, 0))
        return frame

    def _build_operations_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=6)
        self.operations_tree = ttk.Treeview(
            frame,
            columns=("layer", "index", "op"),
            show="headings",
            height=7,
        )
        self.operations_tree.heading("layer", text="Layer")
        self.operations_tree.heading("index", text="#")
        self.operations_tree.heading("op", text="Operation")
        self.operations_tree.column("layer", width=120)
        self.operations_tree.column("index", width=40)
        self.operations_tree.column("op", width=120)
        self.operations_tree.pack(fill=tk.BOTH, expand=True)

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(buttons, text="Add", command=self.add_operation).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Edit", command=self.edit_operation).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(buttons, text="Delete", command=self.delete_operation).pack(side=tk.LEFT, padx=(6, 0))
        return frame

    def new_document(self) -> None:
        self.current_path = None
        self.set_document(default_document())

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Pixel Art JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path) -> None:
        try:
            document = load_document(path)
            render_document(document)
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc), parent=self.root)
            return
        self.current_path = path
        self.set_document(document)

    def save_file(self) -> None:
        if self.current_path is None:
            self.save_file_as()
            return
        self._save_to_path(self.current_path)

    def _save_to_path(self, path: Path) -> bool:
        if not self.apply_json(show_success=False):
            return False
        try:
            save_document(self.document, path)
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror("Save failed", str(exc), parent=self.root)
            return False
        self.current_path = path
        return True

    def save_file_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save Pixel Art JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        self._save_to_path(Path(path))

    def export_png(self) -> None:
        if not self.apply_json(show_success=False):
            return
        path = filedialog.asksaveasfilename(
            title="Export PNG",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            save_png(self.document, path, scale=self.preview_scale.get())
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self.root)

    def set_document(self, document: dict[str, Any]) -> None:
        self.document = document
        self.json_text.delete("1.0", "end")
        self.json_text.insert("1.0", pretty_json(document))
        self.refresh_lists()
        self.render_preview()

    def apply_json(self, show_success: bool = True) -> bool:
        try:
            document = parse_json(self.json_text.get("1.0", "end"))
            render_document(document)
        except Exception as exc:
            messagebox.showerror("Invalid document", str(exc), parent=self.root)
            return False
        self.document = document
        self.refresh_lists()
        self.render_preview()
        if show_success:
            self.root.bell()
        return True

    def _set_document_if_valid(self, document: dict[str, Any]) -> bool:
        try:
            render_document(document)
        except Exception as exc:
            messagebox.showerror("Invalid document", str(exc), parent=self.root)
            return False
        self.set_document(document)
        return True

    def format_json(self) -> None:
        if self.apply_json(show_success=False):
            self.json_text.delete("1.0", "end")
            self.json_text.insert("1.0", pretty_json(self.document))

    def render_preview(self) -> None:
        self.preview_canvas.delete("preview")
        self.preview_item = None
        self.preview_error_item = None
        try:
            scale = self.preview_scale.get()
            image = render_document(self.document, scale=scale)
            self.preview_photo = ImageTk.PhotoImage(image)
            self.preview_item = self.preview_canvas.create_image(
                0,
                0,
                image=self.preview_photo,
                anchor="nw",
                tags=("preview",),
            )
            self._position_preview()
        except Exception as exc:
            self.preview_photo = None
            self.preview_error_item = self.preview_canvas.create_text(
                12,
                12,
                anchor="nw",
                text=str(exc),
                fill="#8b0000",
                width=320,
                tags=("preview",),
            )
            self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("preview"))

    def _position_preview(self) -> None:
        if self.preview_item is None or self.preview_photo is None:
            if self.preview_error_item is not None:
                self.preview_canvas.coords(self.preview_error_item, 12, 12)
                self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("preview"))
            return

        canvas_width = max(self.preview_canvas.winfo_width(), 1)
        canvas_height = max(self.preview_canvas.winfo_height(), 1)
        image_width = self.preview_photo.width()
        image_height = self.preview_photo.height()
        x = max((canvas_width - image_width) // 2, 0)
        y = max((canvas_height - image_height) // 2, 0)

        self.preview_canvas.coords(self.preview_item, x, y)
        self.preview_canvas.configure(
            scrollregion=(
                0,
                0,
                max(canvas_width, image_width),
                max(canvas_height, image_height),
            )
        )

    def refresh_lists(self) -> None:
        for item in self.palette_tree.get_children():
            self.palette_tree.delete(item)
        palette = self.document.get("palette", {})
        if isinstance(palette, dict):
            for name, value in palette.items():
                self.palette_tree.insert("", "end", iid=name, values=(name, value))

        for item in self.operations_tree.get_children():
            self.operations_tree.delete(item)
        for entry in self._operation_entries():
            iid, layer_name, index, op_name = entry
            self.operations_tree.insert("", "end", iid=iid, values=(layer_name, index, op_name))

    def add_palette_color(self) -> None:
        if not self.apply_json(show_success=False):
            return
        name = simpledialog.askstring("Add color", "Palette name:", parent=self.root)
        if not name:
            return
        value = simpledialog.askstring("Add color", "Color value (#RRGGBB or #RRGGBBAA):", parent=self.root)
        if not value:
            return
        candidate = deepcopy(self.document)
        candidate.setdefault("palette", {})[name] = value
        self._set_document_if_valid(candidate)

    def edit_palette_color(self) -> None:
        if not self.apply_json(show_success=False):
            return
        selection = self.palette_tree.selection()
        if not selection:
            return
        name = selection[0]
        candidate = deepcopy(self.document)
        palette = candidate.setdefault("palette", {})
        value = simpledialog.askstring(
            "Edit color",
            f"Color value for {name}:",
            initialvalue=str(palette.get(name, "")),
            parent=self.root,
        )
        if value:
            palette[name] = value
            self._set_document_if_valid(candidate)

    def delete_palette_color(self) -> None:
        if not self.apply_json(show_success=False):
            return
        selection = self.palette_tree.selection()
        if not selection:
            return
        name = selection[0]
        if messagebox.askyesno("Delete color", f"Delete palette color {name}?", parent=self.root):
            candidate = deepcopy(self.document)
            candidate.get("palette", {}).pop(name, None)
            self._set_document_if_valid(candidate)

    def add_operation(self) -> None:
        if not self.apply_json(show_success=False):
            return
        palette = self.document.get("palette", {})
        template = {
            "op": "rect",
            "color": next(iter(palette), "color"),
            "x": 0,
            "y": 0,
            "w": 4,
            "h": 4,
        }
        dialog = JsonDialog(self.root, "Add operation", template)
        if dialog.result is None:
            return
        candidate = deepcopy(self.document)
        container = self._default_operation_container(candidate)
        container.append(dialog.result)
        self._set_document_if_valid(candidate)

    def edit_operation(self) -> None:
        if not self.apply_json(show_success=False):
            return
        selected = self.operations_tree.selection()
        if not selected:
            return
        container, index = self._operation_container_for_iid(selected[0])
        dialog = JsonDialog(self.root, "Edit operation", container[index])
        if dialog.result is None:
            return
        candidate = deepcopy(self.document)
        container, index = self._operation_container_for_iid(selected[0], candidate)
        container[index] = dialog.result
        self._set_document_if_valid(candidate)

    def delete_operation(self) -> None:
        if not self.apply_json(show_success=False):
            return
        selected = self.operations_tree.selection()
        if not selected:
            return
        container, index = self._operation_container_for_iid(selected[0])
        if messagebox.askyesno("Delete operation", "Delete selected operation?", parent=self.root):
            candidate = deepcopy(self.document)
            container, index = self._operation_container_for_iid(selected[0], candidate)
            del container[index]
            self._set_document_if_valid(candidate)

    def _operation_entries(self) -> list[tuple[str, str, int, str]]:
        entries: list[tuple[str, str, int, str]] = []
        layers = self.document.get("layers")
        if isinstance(layers, list):
            for layer_index, layer in enumerate(layers):
                if not isinstance(layer, dict):
                    continue
                layer_name = str(layer.get("name", f"Layer {layer_index + 1}"))
                operations = layer.get("operations", [])
                if not isinstance(operations, list):
                    continue
                for op_index, operation in enumerate(operations):
                    op_name = operation.get("op", "?") if isinstance(operation, dict) else "?"
                    entries.append((f"layer:{layer_index}:{op_index}", layer_name, op_index, str(op_name)))
        else:
            operations = self.document.get("operations", [])
            if isinstance(operations, list):
                for op_index, operation in enumerate(operations):
                    op_name = operation.get("op", "?") if isinstance(operation, dict) else "?"
                    entries.append((f"top:{op_index}", "operations", op_index, str(op_name)))
        return entries

    def _default_operation_container(self, document: dict[str, Any] | None = None) -> list[Any]:
        if document is None:
            document = self.document
        layers = document.get("layers")
        if isinstance(layers, list):
            if not layers:
                layers.append({"name": "Layer 1", "operations": []})
            layer = layers[0]
            if not isinstance(layer, dict):
                layers[0] = {"name": "Layer 1", "operations": []}
                layer = layers[0]
            operations = layer.setdefault("operations", [])
            if not isinstance(operations, list):
                layer["operations"] = []
                operations = layer["operations"]
            return operations
        operations = document.setdefault("operations", [])
        if not isinstance(operations, list):
            document["operations"] = []
            operations = document["operations"]
        return operations

    def _operation_container_for_iid(
        self,
        iid: str,
        document: dict[str, Any] | None = None,
    ) -> tuple[list[Any], int]:
        if document is None:
            document = self.document
        if iid.startswith("layer:"):
            _, layer_index_text, op_index_text = iid.split(":")
            layer = document["layers"][int(layer_index_text)]
            return layer["operations"], int(op_index_text)
        if iid.startswith("top:"):
            _, op_index_text = iid.split(":")
            return document["operations"], int(op_index_text)
        raise ValueError(f"Unknown operation id: {iid}")


def main(input_path: str | Path | None = None) -> None:
    root = tk.Tk()
    path = Path(input_path) if input_path else None
    PixelArtEditor(root, path)
    root.mainloop()


if __name__ == "__main__":
    main()
