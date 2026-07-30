from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

from pixelscope.core.image_document import ImageDocument


class PixelInspector(QWidget):
    """Compact current/compare pixel value panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        layout = QFormLayout(self)
        for key, title in (
            ("coordinate", "Coordinate"),
            ("document", "Document"),
            ("dtype", "dtype"),
            ("value", "Value"),
            ("a", "A"),
            ("b", "B"),
            ("signed", "Signed A-B"),
            ("absolute", "Absolute"),
        ):
            label = QLabel("—")
            label.setTextInteractionFlags(label.textInteractionFlags())
            self._labels[key] = label
            layout.addRow(title, label)

    @staticmethod
    def _format(value: object) -> str:
        if isinstance(value, tuple):
            return "(" + ", ".join(str(item) for item in value) + ")"
        return str(value)

    def update_document(self, document: ImageDocument, x: int, y: int) -> None:
        value = document.pixel_at(x, y)
        self._labels["coordinate"].setText(f"{x}, {y}")
        self._labels["document"].setText(document.display_name)
        self._labels["dtype"].setText(str(document.original_dtype))
        self._labels["value"].setText("—" if value is None else self._format(value))
        for key in ("a", "b", "signed", "absolute"):
            self._labels[key].setText("—")

    def update_compare(self, a: ImageDocument, b: ImageDocument, x: int, y: int) -> None:
        value_a, value_b = a.pixel_at(x, y), b.pixel_at(x, y)
        self._labels["coordinate"].setText(f"{x}, {y}")
        self._labels["document"].setText(f"{a.display_name} / {b.display_name}")
        self._labels["dtype"].setText(f"{a.original_dtype} / {b.original_dtype}")
        self._labels["value"].setText("—")
        self._labels["a"].setText(self._format(value_a))
        self._labels["b"].setText(self._format(value_b))
        if value_a is None or value_b is None:
            self._labels["signed"].setText("—")
            self._labels["absolute"].setText("—")
            return
        if isinstance(value_a, tuple) and isinstance(value_b, tuple):
            signed_tuple = tuple(
                int(left) - int(right) for left, right in zip(value_a, value_b, strict=True)
            )
            absolute_tuple = tuple(abs(value) for value in signed_tuple)
            self._labels["signed"].setText(self._format(signed_tuple))
            self._labels["absolute"].setText(self._format(absolute_tuple))
            return
        signed_scalar = int(value_a) - int(value_b)  # type: ignore[arg-type]
        self._labels["signed"].setText(self._format(signed_scalar))
        self._labels["absolute"].setText(self._format(abs(signed_scalar)))

    def value_text(self) -> str:
        """Test-facing readout of the current primary value."""

        return self._labels["value"].text()
