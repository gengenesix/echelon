"""
Windows packaging helper for Echelon.
Run this ON a Windows machine with Python + PyInstaller installed.
Or use GitHub Actions for cross-compilation.
"""
import subprocess
import sys
from pathlib import Path

def build_windows():
    print("Building Echelon for Windows...")
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=Echelon',
        '--onedir',
        '--windowed',
        '--icon=assets/icons/echelon.ico',
        '--add-data=assets/styles/theme.qss;assets/styles',
        '--add-data=assets/icons/*.png;assets/icons',
        '--add-data=assets/icons/*.ico;assets/icons',
        '--add-data=models/*.onnx;models',
        '--add-data=models/models;models/models',
        '--add-data=vendor;vendor',
        '--add-data=data;data',
        '--hidden-import=PyQt6.QtCore',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtWidgets',
        '--hidden-import=cv2',
        '--hidden-import=onnxruntime',
        '--hidden-import=insightface',
        '--hidden-import=PIL',
        '--hidden-import=psutil',
        '--hidden-import=pyvirtualcam',
        '--clean',
        '--noconfirm',
        'main.py'
    ]
    subprocess.run(cmd, check=True)
    print("✅ Windows build complete: dist/Echelon/Echelon.exe")

if __name__ == '__main__':
    build_windows()
