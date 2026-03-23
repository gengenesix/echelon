# Echelon
Real-time face swap for video calls — WhatsApp, Zoom, Meet, Teams, Discord.
Works on Linux, Windows, and macOS.

## Install

### Linux — AppImage (no install needed)
```bash
chmod +x Echelon-x86_64.AppImage
./Echelon-x86_64.AppImage
```

### Linux — Deb package
```bash
sudo dpkg -i echelon_2.0.0_amd64.deb
```

### Windows
1. Download `Echelon-Windows.zip`
2. Extract to any folder
3. Run `Echelon.exe`
4. On first launch, models download automatically
> Note: Virtual camera requires OBS Virtual Camera or similar on Windows

### macOS
1. Download `Echelon-macOS.dmg`
2. Drag Echelon to Applications
3. Right-click → Open (first time, to bypass Gatekeeper)
4. On first launch, models download automatically
> Note: Virtual camera requires OBS Virtual Camera on macOS

### Linux — From source
```bash
cd ~/xeroclaw/echelon
chmod +x setup.sh && ./setup.sh
./run.sh
```

## Requirements
- 8GB RAM minimum
- Webcam
- NVIDIA GPU optional (significantly improves performance)
- Linux: Ubuntu 20.04+ / Debian 11+ with Python 3.10+

## Using Echelon in Video Calls
1. Launch Echelon and upload a source face photo
2. Click "Start Echelon"
3. In your video call app: Settings → Camera → Select "Echelon Camera"
4. Your swapped face is now live in the call

## Performance Tips
- Use "Speed" mode on machines without a dedicated GPU
- Close other GPU-heavy applications while Echelon is running

## Troubleshooting

**Virtual camera not found (Linux):**
```bash
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="Echelon Camera" exclusive_caps=1
```

**Model download failed:**
Download `inswapper_128.onnx` manually from HuggingFace and place in `~/xeroclaw/echelon/models/`

## Building from Source

### Linux packages
```bash
cd ~/xeroclaw/echelon
source venv/bin/activate
pip install pyinstaller
pyinstaller echelon.spec --clean --noconfirm
bash package_appimage.sh   # builds Echelon-x86_64.AppImage
bash package_deb.sh        # builds echelon_2.0.0_amd64.deb
```

### Windows (run on Windows)
```bash
python package_windows.py
```

### macOS (run on macOS)
```bash
bash package_macos.sh
```

## Responsible Use
Echelon is for entertainment and creative use. Do not use it to deceive, defraud, or harm others.
