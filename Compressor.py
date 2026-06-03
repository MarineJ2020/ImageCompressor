import io
import os
import subprocess
import sys
import tempfile
from PIL import Image, ImageGrab, ImageQt
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSlider,
    QMessageBox,
    QComboBox,
    QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent

PANEL_STYLE = """
    QLabel {
        border: 2px dashed #555;
        border-radius: 12px;
        padding: 20px;
        background: #1e1e1e;
        color: #888;
        font-size: 15px;
    }
"""

PRESET_INACTIVE = """
    QPushButton {
        background: transparent;
        color: #3b82f6;
        border: 1.5px solid #3b82f6;
        border-radius: 14px;
        padding: 6px 14px;
        font-size: 13px;
    }
    QPushButton:hover { background: #1e3a5f; }
"""

PRESET_ACTIVE = """
    QPushButton {
        background: #3b82f6;
        color: white;
        border: 1.5px solid #3b82f6;
        border-radius: 14px;
        padding: 6px 14px;
        font-size: 13px;
    }
"""

ACTION_STYLE = """
    QPushButton {
        background: #3b82f6;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 12px;
        font-size: 14px;
    }
    QPushButton:hover { background: #2563eb; }
"""


class ImageCompressor(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Image Compressor")
        self.setMinimumSize(900, 700)

        self.image = None
        self.compressed_data = None
        self._source_format = "Unknown"
        self._active_preset_btn = None

        self.setAcceptDrops(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # ── Before / After splitter ──────────────────────────────────────────
        self.before_label = QLabel("Drag & drop, paste CTRL+V, or Upload")
        self.before_label.setAlignment(Qt.AlignCenter)
        self.before_label.setStyleSheet(PANEL_STYLE)
        self.before_label.setMinimumSize(300, 380)

        self.after_label = QLabel("Compressed preview")
        self.after_label.setAlignment(Qt.AlignCenter)
        self.after_label.setStyleSheet(PANEL_STYLE)
        self.after_label.setMinimumSize(300, 380)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.before_label)
        self.splitter.addWidget(self.after_label)
        self.splitter.setSizes([450, 450])
        self.splitter.setHandleWidth(6)
        self.splitter.setStyleSheet("""
            QSplitter::handle { background: #3b82f6; border-radius: 3px; }
        """)

        # ── Meta label (source info, populated on load) ──────────────────────
        self.meta_label = QLabel("")
        self.meta_label.setAlignment(Qt.AlignCenter)
        self.meta_label.setStyleSheet("color: #888; font-size: 12px;")

        # ── Compression stats label ──────────────────────────────────────────
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: white; font-size: 14px;")

        # ── Presets ──────────────────────────────────────────────────────────
        preset_layout = QHBoxLayout()
        preset_label = QLabel("Presets:")
        preset_label.setStyleSheet("color: #aaa; font-size: 13px;")
        preset_layout.addWidget(preset_label)

        presets = [
            ("Web",      "WEBP", 75),
            ("Photo",    "JPEG", 82),
            ("Email",    "JPEG", 55),
            ("Lossless", "PNG",  100),
        ]
        self._preset_btns = []
        for name, fmt, q in presets:
            btn = QPushButton(name)
            btn.setStyleSheet(PRESET_INACTIVE)
            btn.clicked.connect(lambda checked, f=fmt, qv=q, b=btn: self.apply_preset(f, qv, b))
            preset_layout.addWidget(btn)
            self._preset_btns.append(btn)

        preset_layout.addStretch()

        # ── Quality slider ───────────────────────────────────────────────────
        quality_layout = QHBoxLayout()
        self.quality_label = QLabel("Quality: 92")
        self.quality_label.setStyleSheet("color: white;")
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setMinimum(10)
        self.quality_slider.setMaximum(100)
        self.quality_slider.setValue(92)
        self.quality_slider.valueChanged.connect(self.update_quality)
        quality_layout.addWidget(self.quality_label)
        quality_layout.addWidget(self.quality_slider)

        # ── Format dropdown ──────────────────────────────────────────────────
        self.format_dropdown = QComboBox()
        self.format_dropdown.addItems(["WEBP", "JPEG", "PNG"])
        self.format_dropdown.currentIndexChanged.connect(self._on_format_changed)
        self.format_dropdown.setStyleSheet("""
            QComboBox {
                background: #2a2a2a;
                color: white;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 6px;
                font-size: 14px;
            }
            QComboBox QAbstractItemView {
                background: #2a2a2a;
                color: white;
                selection-background-color: #3b82f6;
            }
        """)

        # ── Action buttons ───────────────────────────────────────────────────
        button_layout = QHBoxLayout()
        self.upload_btn = QPushButton("Upload Image")
        self.upload_btn.clicked.connect(self.upload_image)
        self.paste_btn = QPushButton("Copy to Clipboard")
        self.paste_btn.clicked.connect(self.copy_to_clipboard)
        self.save_btn = QPushButton("Save Compressed")
        self.save_btn.clicked.connect(self.save_image)
        for btn in [self.upload_btn, self.paste_btn, self.save_btn]:
            btn.setStyleSheet(ACTION_STYLE)
        button_layout.addWidget(self.upload_btn)
        button_layout.addWidget(self.paste_btn)
        button_layout.addWidget(self.save_btn)

        # ── Assemble layout ──────────────────────────────────────────────────
        layout.addWidget(self.splitter)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.info_label)
        layout.addLayout(preset_layout)
        layout.addLayout(quality_layout)
        layout.addWidget(self.format_dropdown)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.setStyleSheet("""
            QWidget { background: #121212; }
            QMessageBox { background: #1e1e1e; }
            QMessageBox QLabel { color: #f0f0f0; font-size: 14px; background: transparent; }
            QMessageBox QPushButton {
                background: #3b82f6; color: white; border: none;
                border-radius: 6px; padding: 8px 20px; font-size: 13px;
            }
            QMessageBox QPushButton:hover { background: #2563eb; }
        """)

    # ── Preset handling ──────────────────────────────────────────────────────

    def apply_preset(self, fmt, quality, btn):
        if self._active_preset_btn:
            self._active_preset_btn.setStyleSheet(PRESET_INACTIVE)
        btn.setStyleSheet(PRESET_ACTIVE)
        self._active_preset_btn = btn

        self.format_dropdown.blockSignals(True)
        self.format_dropdown.setCurrentText(fmt)
        self.format_dropdown.blockSignals(False)

        self.quality_slider.blockSignals(True)
        self.quality_slider.setValue(quality)
        self.quality_slider.blockSignals(False)
        self.quality_label.setText(f"Quality: {quality}")

        if self.image:
            self.compress_preview()

    def _on_format_changed(self):
        if self._active_preset_btn:
            self._active_preset_btn.setStyleSheet(PRESET_INACTIVE)
            self._active_preset_btn = None
        if self.image:
            self.compress_preview()

    # ── Quality ──────────────────────────────────────────────────────────────

    def update_quality(self):
        value = self.quality_slider.value()
        self.quality_label.setText(f"Quality: {value}")
        if self._active_preset_btn:
            self._active_preset_btn.setStyleSheet(PRESET_INACTIVE)
            self._active_preset_btn = None
        if self.image:
            self.compress_preview()

    # ── Image loading ────────────────────────────────────────────────────────

    def upload_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            raw = Image.open(file_path)
            self._source_format = raw.format or "Unknown"
            self.image = raw.convert("RGBA")
            self.show_image()
            self.compress_preview()

    def paste_image(self):
        clipboard_image = ImageGrab.grabclipboard()
        if isinstance(clipboard_image, Image.Image):
            self._source_format = "Clipboard"
            self.image = clipboard_image.convert("RGBA")
            self.show_image()
            self.compress_preview()
        else:
            QMessageBox.warning(self, "No Image", "Clipboard does not contain an image.")

    # ── Display ──────────────────────────────────────────────────────────────

    def _scale_pixmap(self, pil_image, label):
        qt_image = ImageQt.ImageQt(pil_image)
        pixmap = QPixmap.fromImage(qt_image)
        return pixmap.scaled(
            label.width(), label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )

    def show_image(self):
        if not self.image:
            return
        self.before_label.setPixmap(self._scale_pixmap(self.image, self.before_label))
        w, h = self.image.size
        self.meta_label.setText(
            f"{w} × {h} px   |   {self.image.mode}   |   Source: {self._source_format}"
        )

    def compress_preview(self):
        if not self.image:
            return

        quality = self.quality_slider.value()
        fmt = self.format_dropdown.currentText()

        save_kwargs = {}
        if fmt in ["WEBP", "JPEG"]:
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        if fmt == "WEBP":
            save_kwargs["method"] = 6

        image_to_save = self.image

        if fmt == "JPEG":
            image_to_save = image_to_save.convert("RGB")

        buffer = io.BytesIO()
        image_to_save.save(buffer, format=fmt, **save_kwargs)
        self.compressed_data = buffer.getvalue()

        preview_buffer = io.BytesIO(self.compressed_data)
        preview_image = Image.open(preview_buffer).convert("RGBA")
        self.after_label.setPixmap(self._scale_pixmap(preview_image, self.after_label))

        uncompressed_size = self.get_original_size()
        compressed_size = len(self.compressed_data)
        reduction = 100 - ((compressed_size / uncompressed_size) * 100)

        self.info_label.setText(
            f"Uncompressed: {self.format_size(uncompressed_size)}   |   "
            f"Compressed: {self.format_size(compressed_size)}   |   "
            f"Saved: {reduction:.1f}%"
        )

    def get_original_size(self):
        temp = io.BytesIO()
        self.image.save(temp, format="PNG")
        return len(temp.getvalue())

    # ── Output ───────────────────────────────────────────────────────────────

    def copy_to_clipboard(self):
        if not self.compressed_data:
            QMessageBox.warning(self, "No Image", "Please upload or paste an image first.")
            return

        fmt = self.format_dropdown.currentText().lower()
        fd, temp_path = tempfile.mkstemp(suffix=f".{fmt}")
        with os.fdopen(fd, "wb") as f:
            f.write(self.compressed_data)

        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f'Set-Clipboard -Path "{temp_path}"'],
            capture_output=True,
        )

        if result.returncode == 0:
            QMessageBox.information(
                self, "Copied",
                f"Compressed {fmt.upper()} file copied to clipboard.\n"
                "Paste it in File Explorer or any app that accepts file pastes."
            )
        else:
            QMessageBox.warning(self, "Error", "Failed to copy file to clipboard.")

    def save_image(self):
        if not self.compressed_data:
            QMessageBox.warning(self, "No Image", "Please upload or paste an image first.")
            return

        fmt = self.format_dropdown.currentText().lower()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", f"compressed.{fmt}", f"{fmt.upper()} Files (*.{fmt})"
        )

        if path:
            with open(path, "wb") as f:
                f.write(self.compressed_data)
            QMessageBox.information(self, "Saved", "Compressed image saved successfully.")

    def format_size(self, size):
        for unit in ["B", "KB", "MB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"

    # ── Events ───────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.image:
            self.before_label.setPixmap(self._scale_pixmap(self.image, self.before_label))
        if self.compressed_data:
            preview_buffer = io.BytesIO(self.compressed_data)
            preview_image = Image.open(preview_buffer).convert("RGBA")
            self.after_label.setPixmap(self._scale_pixmap(preview_image, self.after_label))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith((".png", ".jpg", ".jpeg", ".webp")) for u in urls):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                raw = Image.open(file_path)
                self._source_format = raw.format or "Unknown"
                self.image = raw.convert("RGBA")
                self.show_image()
                self.compress_preview()
                break

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V:
            self.paste_image()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageCompressor()
    window.show()
    sys.exit(app.exec())
