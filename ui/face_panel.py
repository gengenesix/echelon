from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFileDialog, QComboBox, QLineEdit,
                              QSizePolicy, QInputDialog)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap
import cv2
from ui.widgets import SectionLabel, Divider

_GALLERY_PLACEHOLDER = "— select saved face —"


class FacePanel(QWidget):
    face_selected = pyqtSignal(str)             # path — for detection
    gallery_save_requested = pyqtSignal(str)    # name — save current face
    gallery_load_requested = pyqtSignal(str)    # name — load saved face
    gallery_delete_requested = pyqtSignal(str)  # name — delete saved face

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(SectionLabel("SOURCE FACE"))

        self._img_label = QLabel()
        self._img_label.setFixedSize(180, 180)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setStyleSheet(
            "border: 1px dashed #252632; border-radius: 10px; "
            "background-color: #111218; color: #50516A; font-size: 12px;"
        )
        self._img_label.setText("Drop photo here\nor click to browse")
        layout.addWidget(self._img_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._upload_btn = QPushButton("Upload Photo")
        self._upload_btn.setObjectName("uploadBtn")
        self._upload_btn.clicked.connect(self._on_upload_clicked)
        layout.addWidget(self._upload_btn)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        layout.addWidget(Divider())

        # Gallery section
        layout.addWidget(SectionLabel("GALLERY"))

        self._gallery_combo = QComboBox()
        self._gallery_combo.addItem(_GALLERY_PLACEHOLDER)
        layout.addWidget(self._gallery_combo)

        gallery_btns = QHBoxLayout()
        self._load_btn = QPushButton("Load")
        self._load_btn.setFixedHeight(28)
        self._load_btn.clicked.connect(self._on_gallery_load)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setFixedHeight(28)
        self._delete_btn.setStyleSheet("color: #FF5566;")
        self._delete_btn.clicked.connect(self._on_gallery_delete)
        gallery_btns.addWidget(self._load_btn)
        gallery_btns.addWidget(self._delete_btn)
        layout.addLayout(gallery_btns)

        self._save_btn = QPushButton("Save Current to Gallery")
        self._save_btn.setFixedHeight(28)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_gallery_save)
        layout.addWidget(self._save_btn)

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
        img = cv2.resize(img, (170, 170))
        from PyQt6.QtGui import QImage
        qimg = QImage(img.data, 170, 170, 3 * 170, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self._img_label.setPixmap(pixmap)
        self._img_label.setStyleSheet(
            "border: 1px solid #22D98F; border-radius: 10px; "
            "background-color: #111218;"
        )
        self._status_label.setText("✓ Face detected")
        self._status_label.setStyleSheet("color: #22D98F; font-size: 12px;")
        self._save_btn.setEnabled(True)

    def show_error(self, message: str):
        self._status_label.setText(f"✗ {message}")
        self._status_label.setStyleSheet("color: #FF5CA8; font-size: 12px;")
        self._img_label.setText("Drop photo here\nor click to browse")
        self._img_label.setPixmap(QPixmap())
        self._img_label.setStyleSheet(
            "border: 1px dashed #FF5CA8; border-radius: 10px; "
            "background-color: #111218; color: #50516A; font-size: 12px;"
        )
        self._save_btn.setEnabled(False)

    def update_gallery_list(self, faces: list):
        """Refresh dropdown from gallery list of dicts."""
        current = self._gallery_combo.currentText()
        self._gallery_combo.clear()
        self._gallery_combo.addItem(_GALLERY_PLACEHOLDER)
        for f in faces:
            self._gallery_combo.addItem(f["name"])
        # Restore selection if still present
        idx = self._gallery_combo.findText(current)
        if idx >= 0:
            self._gallery_combo.setCurrentIndex(idx)
