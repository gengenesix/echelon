#!/bin/bash
set -e

echo "==> Setting up Echelon..."

echo "==> Installing apt packages..."
sudo apt-get update -q
sudo apt-get install -y python3-pip python3-venv python3-dev build-essential \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    v4l2loopback-dkms v4l2loopback-utils ffmpeg cmake git curl wget \
    libgtk-3-dev pkg-config

echo "==> Loading v4l2loopback..."
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="Echelon Camera" exclusive_caps=1 || true

echo "==> Creating virtual environment..."
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate

echo "==> Installing pip packages..."
pip install --upgrade pip setuptools wheel
pip install numpy opencv-python Pillow requests tqdm psutil
pip install onnxruntime || true
pip install insightface onnx
pip install PyQt6
pip install pyvirtualcam
pip install scipy scikit-image imageio

echo "==> Verifying imports..."
python3 -c "import cv2; print('OpenCV OK:', cv2.__version__)"
python3 -c "import onnxruntime; print('ONNX Runtime OK')"
python3 -c "import insightface; print('InsightFace OK')"
python3 -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')"
python3 -c "import pyvirtualcam; print('pyvirtualcam OK')"

echo ""
echo "✅ Echelon setup complete. Run: source venv/bin/activate && python3 main.py"
