from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFileDialog, QComboBox, QFrame,
                              QInputDialog)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QImage
import cv2
from ui.widgets import SectionCard

_GALLERY_PLACEHOLDER = "— select saved face —"


class _ClickableFrame(QFrame):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class FacePanel(QWidget):
    face_selected = pyqtSignal(str)
    gallery_save_requested = pyqtSignal(str)
    gallery_load_requested = pyqtSignal(str)
    gallery_delete_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── Source Face Section ──
        face_card = SectionCard("Source Face")

        # Drop zone (clickable)
        self._drop_zone = _ClickableFrame()
        self._drop_zone.setObjectName("dropZone")
        self._drop_zone.setFixedHeight(130)
        self._drop_zone.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drop_zone.clicked.connect(self._on_upload_clicked)

        drop_layout = QVBoxLayout(self._drop_zone)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.setSpacing(4)

        self._drop_icon = QLabel("📷")
        self._drop_icon.setStyleSheet("font-size: 28px; background: transparent; color: #3A3B4E;")
        self._drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self._drop_icon)

        self._drop_hint = QLabel("Drop photo or click to browse")
        self._drop_hint.setStyleSheet("color: #6B7094; font-size: 11px; background: transparent;")
        self._drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self._drop_hint)

        self._img_label = QLabel()
        self._img_label.setFixedSize(110, 110)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setStyleSheet("background: transparent; border: none;")
        self._img_label.hide()
        drop_layout.addWidget(self._img_label, alignment=Qt.AlignmentFlag.AlignCenter)

        face_card.add_widget(self._drop_zone)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("font-size: 11px; color: #6B7094;")
        face_card.add_widget(self._status_label)

        upload_row = QHBoxLayout()
        self._upload_btn = QPushButton("Upload Photo")
        self._upload_btn.clicked.connect(self._on_upload_clicked)
        upload_row.addWidget(self._upload_btn)
        face_card.add_layout(upload_row)

        layout.addWidget(face_card)

        # ── Gallery Section ──
        gallery_card = SectionCard("Gallery")

        self._gallery_combo = QComboBox()
        self._gallery_combo.addItem(_GALLERY_PLACEHOLDER)
        gallery_card.add_widget(self._gallery_combo)

        gallery_btns = QHBoxLayout()
        gallery_btns.setSpacing(6)
        self._load_btn = QPushButton("Load")
        self._load_btn.clicked.connect(self._on_gallery_load)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setStyleSheet("color: #FF4D7A;")
        self._delete_btn.clicked.connect(self._on_gallery_delete)
        gallery_btns.addWidget(self._load_btn)
        gallery_btns.addWidget(self._delete_btn)
        gallery_card.add_layout(gallery_btns)

        self._save_btn = QPushButton("Save Current to Gallery")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_gallery_save)
        gallery_card.add_widget(self._save_btn)

        layout.addWidget(gallery_card)

    def _on_upload_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Face Photo", "",
            "Images (*.jpg *.jpeg *.png *.webp *.bmp)"
        )
        if path:
            self.face_selected.emit(path)

    def _on_gallery_load(self):
        name = self._gallery_combo.currentText()
        if name and name != _GALLERY_PLACEHOLDER:
            self.gallery_load_requested.emit(name)

    def _on_gallery_delete(self):
        name = self._gallery_combo.currentText()
        if name and name != _GALLERY_PLACEHOLDER:
            self.gallery_delete_requested.emit(name)

    def _on_gallery_save(self):
        name, ok = QInputDialog.getText(self, "Save to Gallery", "Face name (e.g. Alice):")
        if ok and name.strip():
            self.gallery_save_requested.emit(name.strip())

    # ── public methods called by MainWindow ─────────────────────────────────

    def show_face_preview(self, image_path: str):
        img = cv2.imread(image_path)
        if img is None:
            self.show_error("Cannot load image")
            return
        h, w = img.shape[:2]
        size = min(h, w)
        y = (h - size) // 2
        x = (w - size) // 2
        img = img[y:y + size, x:x + size]
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (110, 110))
        qimg = QImage(img.data, 110, 110, 3 * 110, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        # Hide placeholder, show image
        self._drop_icon.hide()
        self._drop_hint.hide()
        self._img_label.setPixmap(pixmap)
        self._img_label.show()
        self._drop_zone.setStyleSheet(
            "QFrame#dropZone { background: #0D0E1A; border: 1.5px solid #22D98F; border-radius: 10px; }"
        )
        self._status_label.setText("✓ Face detected")
        self._status_label.setStyleSheet("color: #22D98F; font-size: 11px;")
        self._save_btn.setEnabled(True)

    def show_error(self, message: str):
        self._status_label.setText(f"✗ {message}")
        self._status_label.setStyleSheet("color: #FF4D7A; font-size: 11px;")
        self._img_label.hide()
        self._drop_icon.show()
        self._drop_hint.show()
        self._drop_zone.setStyleSheet(
            "QFrame#dropZone { background: #0D0E1A; border: 1.5px dashed #FF4D7A; border-radius: 10px; }"
        )
        self._save_btn.setEnabled(False)

    def update_gallery_list(self, faces: list):
        current = self._gallery_combo.currentText()
        self._gallery_combo.clear()
        self._gallery_combo.addItem(_GALLERY_PLACEHOLDER)
        for f in faces:
            self._gallery_combo.addItem(f["name"])
        idx = self._gallery_combo.findText(current)
        if idx >= 0:
            self._gallery_combo.setCurrentIndex(idx)
