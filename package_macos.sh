#!/bin/bash
# Run ON macOS with Python + PyInstaller
set -e
cd "$(dirname "$0")"
source venv/bin/activate

pyinstaller \
    --name=Echelon \
    --onedir \
    --windowed \
    --icon=assets/icons/icon_1024.png \
    --osx-bundle-identifier=com.zero.echelon \
    --add-data="assets/styles/theme.qss:assets/styles" \
    --add-data="assets/icons/*.png:assets/icons" \
    --add-data="models/*.onnx:models" \
    --add-data="models/models:models/models" \
    --add-data="vendor:vendor" \
    --add-data="data:data" \
    --hidden-import=PyQt6.QtCore \
    --hidden-import=PyQt6.QtGui \
    --hidden-import=PyQt6.QtWidgets \
    --hidden-import=cv2 \
    --hidden-import=onnxruntime \
    --hidden-import=insightface \
    --hidden-import=PIL \
    --hidden-import=psutil \
    --hidden-import=pyvirtualcam \
    --clean \
    --noconfirm \
    main.py

# Create DMG
if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "Echelon" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --app-drop-link 425 120 \
        --icon "Echelon.app" 175 120 \
        "Echelon-macOS.dmg" \
        "dist/Echelon.app"
    echo "✅ macOS DMG created: Echelon-macOS.dmg"
else
    echo "✅ macOS app created: dist/Echelon.app"
    echo "   Install create-dmg for DMG packaging: brew install create-dmg"
fi
