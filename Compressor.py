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
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage


class ImageCompressor(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Image Compressor")
        self.setMinimumSize(700, 700)

        self.image = None
        self.compressed_data = None

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Preview
        self.preview = QLabel("Paste image with CTRL+V or Upload")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("""
            QLabel {
                border: 2px dashed #555;
                border-radius: 12px;
                padding: 20px;
                background: #1e1e1e;
                color: white;
                font-size: 18px;
            }
        """)
        self.preview.setMinimumHeight(400)

        # Info label
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: white; font-size: 14px;")

        # Quality slider
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

        # Format dropdown
        self.format_dropdown = QComboBox()
        self.format_dropdown.addItems(["WEBP", "JPEG", "PNG"])
        self.format_dropdown.setStyleSheet("""
            QComboBox {
                padding: 6px;
                font-size: 14px;
            }
        """)

        # Buttons
        button_layout = QHBoxLayout()

        self.upload_btn = QPushButton("Upload Image")
        self.upload_btn.clicked.connect(self.upload_image)

        self.paste_btn = QPushButton("Copy to Clipboard")
        self.paste_btn.clicked.connect(self.copy_to_clipboard)

        self.save_btn = QPushButton("Save Compressed")
        self.save_btn.clicked.connect(self.save_image)

        for btn in [self.upload_btn, self.paste_btn, self.save_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background: #3b82f6;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 12px;
                    font-size: 14px;
                }

                QPushButton:hover {
                    background: #2563eb;
                }
            """)

        button_layout.addWidget(self.upload_btn)
        button_layout.addWidget(self.paste_btn)
        button_layout.addWidget(self.save_btn)

        layout.addWidget(self.preview)
        layout.addWidget(self.info_label)
        layout.addLayout(quality_layout)
        layout.addWidget(self.format_dropdown)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.setStyleSheet("""
            QWidget {
                background: #121212;
            }
        """)

    def update_quality(self):
        value = self.quality_slider.value()
        self.quality_label.setText(f"Quality: {value}")

        if self.image:
            self.compress_preview()

    def upload_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)"
        )

        if file_path:
            self.image = Image.open(file_path).convert("RGBA")
            self.show_image()
            self.compress_preview()

    def paste_image(self):
        clipboard_image = ImageGrab.grabclipboard()

        if isinstance(clipboard_image, Image.Image):
            self.image = clipboard_image.convert("RGBA")
            self.show_image()
            self.compress_preview()
        else:
            QMessageBox.warning(self, "No Image", "Clipboard does not contain an image.")

    def copy_to_clipboard(self):
        if not self.compressed_data:
            QMessageBox.warning(self, "No Image", "Please upload or paste an image first.")
            return

        fmt = self.format_dropdown.currentText().lower()

        fd, temp_path = tempfile.mkstemp(suffix=f".{fmt}")
        with os.fdopen(fd, "wb") as f:
            f.write(self.compressed_data)

        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f'Set-Clipboard -Path "{temp_path}"',
            ],
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

    def show_image(self):
        if not self.image:
            return

        qt_image = ImageQt.ImageQt(self.image)
        pixmap = QPixmap.fromImage(qt_image)

        scaled = pixmap.scaled(
            self.preview.width(),
            self.preview.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.preview.setPixmap(scaled)

    def compress_preview(self):
        if not self.image:
            return

        quality = self.quality_slider.value()
        fmt = self.format_dropdown.currentText()

        buffer = io.BytesIO()

        save_kwargs = {}

        if fmt in ["WEBP", "JPEG"]:
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True

        if fmt == "WEBP":
            save_kwargs["method"] = 6

        image_to_save = self.image

        if fmt == "JPEG":
            image_to_save = self.image.convert("RGB")

        image_to_save.save(buffer, format=fmt, **save_kwargs)

        self.compressed_data = buffer.getvalue()

        # Live preview: decode compressed bytes back to display
        preview_buffer = io.BytesIO(self.compressed_data)
        preview_image = Image.open(preview_buffer).convert("RGBA")
        qt_image = ImageQt.ImageQt(preview_image)
        pixmap = QPixmap.fromImage(qt_image)
        scaled = pixmap.scaled(
            self.preview.width(),
            self.preview.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)

        original_size = self.get_original_size()
        compressed_size = len(self.compressed_data)

        reduction = 100 - ((compressed_size / original_size) * 100)

        self.info_label.setText(
            f"Original: {self.format_size(original_size)}   |   "
            f"Compressed: {self.format_size(compressed_size)}   |   "
            f"Saved: {reduction:.1f}%"
        )

    def get_original_size(self):
        temp = io.BytesIO()
        self.image.save(temp, format="PNG")
        return len(temp.getvalue())

    def save_image(self):
        if not self.compressed_data:
            QMessageBox.warning(self, "No Image", "Please upload or paste an image first.")
            return

        fmt = self.format_dropdown.currentText().lower()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            f"compressed.{fmt}",
            f"{fmt.upper()} Files (*.{fmt})"
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

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V:
            self.paste_image()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = ImageCompressor()
    window.show()

    sys.exit(app.exec())