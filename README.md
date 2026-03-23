# ⚡ Echelon — Real-Time Face Swap

**Swap your face in real-time during any video call. Works with Zoom, Google Meet, Discord, WhatsApp, and Teams.**

Created by **Zero** · v2.0.0

---

## 📥 Download & Install

### → [Download Latest Release](https://github.com/gengenesix/echelon/releases/latest)

| Platform | File | How to Install |
|---|---|---|
| 🪟 **Windows** | `Echelon-Setup.exe` | Double-click → click Next → click Finish |
| 🐧 **Linux (any distro)** | `Echelon-x86_64.AppImage` | See Linux instructions below |
| 🐧 **Ubuntu / Debian** | `echelon_2.0.0_amd64.deb` | See Linux instructions below |

---

## 🪟 Windows Install

1. Download `Echelon-Setup.exe` from the [releases page](https://github.com/gengenesix/echelon/releases/latest)
2. Double-click the file
3. Click **Next** → choose install folder → click **Install** → click **Finish**
4. Echelon appears in your Start Menu and on your Desktop
5. Launch it and follow the setup wizard

**To uninstall:** Go to Settings → Apps → search "Echelon" → Uninstall

---

## 🐧 Linux Install

### Option A — AppImage (works on ANY Linux distro, no install needed)

```bash
# Download Echelon-x86_64.AppImage from the releases page, then:
chmod +x Echelon-x86_64.AppImage
./Echelon-x86_64.AppImage
```

Or right-click the file → Properties → tick "Allow executing as program" → double-click to run.

### Option B — .deb package (Ubuntu, Debian, Linux Mint)

```bash
sudo dpkg -i echelon_2.0.0_amd64.deb
# Then launch from your app menu or type: echelon
```

### Virtual Camera Setup (Linux only)

For Echelon to appear as a camera in Zoom/Meet/etc, install v4l2loopback:

```bash
sudo apt install v4l2loopback-dkms   # Ubuntu/Debian
# OR
sudo dnf install v4l2loopback        # Fedora
```

This is a one-time setup. Echelon will detect it automatically.

---

## 💾 USB Drive / Offline Install

All builds are **100% self-contained**. No internet required after download.

1. Download the installer file on any machine with internet
2. Copy it to a USB drive
3. Plug the USB into the target machine
4. Run the installer — everything works offline

---

## 🔄 How to Build New Installers (for developers)

Building is fully automated. Every time you push a new version tag, GitHub automatically builds fresh installers for Windows and Linux.

### To release a new version:

```bash
# 1. Make your changes to the code
# 2. Commit them
git add -A
git commit -m "Your changes"

# 3. Tag the new version
git tag -a v2.1.0 -m "Echelon v2.1.0"

# 4. Push — this triggers the build automatically
git push origin master
git push origin v2.1.0
```

GitHub then builds `Echelon-Setup.exe` and `Echelon-x86_64.AppImage` on real Windows and Linux servers, and publishes them to the [Releases page](https://github.com/gengenesix/echelon/releases) automatically. Takes ~25 minutes.

### To trigger a build without a new version (for testing):

Go to [Actions → Build Echelon](https://github.com/gengenesix/echelon/actions/workflows/build.yml) → click **Run workflow** → click **Run workflow** (green button).

---

## ⚙️ System Requirements

| | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB |
| CPU | Intel i5 (8th gen+) or equivalent | Intel i7 / AMD Ryzen 7 |
| GPU | Not required | Any (CUDA boosts speed) |
| Webcam | Required | HD (1080p) |
| OS | Windows 10+, Ubuntu 20.04+, Debian 11+ | Latest |

---

## 🔧 Features

- ⚡ Real-time face swap at 15-30 FPS (CPU only)
- 👤 Face gallery — save multiple faces, switch with one click
- 🎭 Multi-face support — swap specific people in group calls  
- 🌫️ Background blur
- 🎛️ Performance modes: Speed / Balanced / Quality
- 💾 Preset profiles — save your favourite setups
- ⌨️ Hotkeys: `Space` toggle, `F1` mode, `Esc` minimize
- 🔄 Auto performance tuner for your hardware

---

## 📂 Project Structure

```
echelon/
├── main.py                 # Entry point
├── ui/                     # PyQt6 UI components
├── core/                   # Face detection, pipeline, inference
├── config/                 # Settings management
├── assets/                 # Icons, styles
├── models/                 # AI model downloader
└── .github/workflows/      # CI/CD build pipeline
```

---

*Built with ❤️ by Zero · [GitHub](https://github.com/gengenesix/echelon)*
