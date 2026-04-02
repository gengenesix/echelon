# ⚡ Echelon — Real-Time Face Swap

**Swap your face in real-time during any video call. Works with Zoom, Google Meet, Discord, WhatsApp, and Teams.**

Created by **Zero** · v2.1.0

---

## 📥 Download & Install

### → [Download Latest Release](https://github.com/gengenesix/echelon/releases/latest)

| Platform | File | How to Install |
|---|---|---|
| 🪟 **Windows** | `Echelon-Setup.exe` | Double-click → click Next → click Finish |
| 🐧 **Linux (any distro)** | `Echelon-x86_64.AppImage` | See Linux instructions below |
| 🐧 **Ubuntu / Debian** | `echelon_2.1.0_amd64.deb` | See Linux instructions below |

---

## 🪟 Windows Install

1. Download `Echelon-Setup.exe` from the [releases page](https://github.com/gengenesix/echelon/releases/latest)
2. Double-click the file
3. Click **Next** → choose install folder → click **Install** → click **Finish**
4. Echelon appears in your Start Menu and on your Desktop
5. Launch it and follow the setup wizard — AI models (~600 MB) download automatically on first run

**To uninstall:** Settings → Apps → search "Echelon" → Uninstall

---

## 🐧 Linux Install

### Option A — AppImage (works on ANY Linux distro, no install needed)

```bash
chmod +x Echelon-x86_64.AppImage
./Echelon-x86_64.AppImage
```

Or right-click → Properties → tick "Allow executing as program" → double-click.

### Option B — .deb package (Ubuntu, Debian, Linux Mint)

```bash
sudo dpkg -i echelon_2.1.0_amd64.deb
echelon   # launch from terminal, or find it in your apps menu
```

### Virtual Camera Setup (Linux — required for video calls)

Echelon needs a virtual camera driver to appear in Zoom/Meet/Discord:

```bash
# Install the driver (one-time)
sudo apt install v4l2loopback-dkms   # Ubuntu/Debian
# OR
sudo dnf install v4l2loopback        # Fedora/RHEL

# Load it now
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="Echelon Camera" exclusive_caps=1

# Make it load automatically on every boot
echo "v4l2loopback" | sudo tee /etc/modules-load.d/v4l2loopback.conf
echo 'options v4l2loopback devices=1 video_nr=10 card_label="Echelon Camera" exclusive_caps=1' | sudo tee /etc/modprobe.d/v4l2loopback.conf
```

The `run.sh` launcher tries to load v4l2loopback automatically if not already loaded.

---

## 🆕 What's New in v2.1.0

- ✅ **Drag & drop** — drag a photo directly onto the upload zone
- ✅ **Instant face upload** — detector loaded once, cached for all subsequent uploads (~instant vs 3-5s before)
- ✅ **Faster detection** — 320×320 detection size (3× faster on CPU)
- ✅ **Better model downloads** — 4-5 mirror fallback per file, size validation, zip fallback, retries
- ✅ **Auto v4l2 setup** — `run.sh` tries to load virtual camera driver automatically
- ✅ **Loading indicator** — clear feedback while face detection runs
- ✅ **Fixed silent failures** — upload button no longer stays disabled after errors
- ✅ **ORT optimizations** — full graph optimization, tuned thread counts

---

## 🤔 First Launch — AI Models

On first launch, Echelon downloads two AI models (~600 MB total, one-time only):

| Model | Size | Purpose |
|---|---|---|
| `inswapper_128.onnx` | ~554 MB | Face swap engine |
| `buffalo_l` (5 files) | ~46 MB | Face detection |

These download automatically via the setup wizard. If download fails, the wizard shows a retry button and fallback instructions.

**Manual download (if automatic fails):**
- `inswapper_128.onnx`: https://github.com/facefusion/facefusion-assets/releases/tag/models
- `buffalo_l`: Run `python -c "import insightface; insightface.app.FaceAnalysis(name='buffalo_l').prepare(ctx_id=-1)"`

Place `inswapper_128.onnx` in your Echelon `models/` folder.

---

## 💾 USB Drive / Offline Install

All builds are **100% self-contained** after first model download.

1. Download the installer on any machine with internet
2. Copy to a USB drive
3. Install on the target machine — models still need internet on first run

---

## 🔄 Building New Releases (developers)

Building is fully automated via GitHub Actions.

```bash
# Make changes, commit, then tag and push:
git add -A && git commit -m "your changes"
git tag v2.2.0
git push origin master
git push origin v2.2.0
```

GitHub builds Windows `.exe` + Linux `.AppImage` + `.deb` automatically in ~25 minutes and publishes to [Releases](https://github.com/gengenesix/echelon/releases).

To trigger manually: [Actions → Build Echelon → Run workflow](https://github.com/gengenesix/echelon/actions/workflows/build.yml)

---

## ⚙️ System Requirements

| | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB |
| CPU | Intel i5 (8th gen+) | Intel i7 / AMD Ryzen 7 |
| GPU | Not required | CUDA GPU (boosts FPS) |
| Webcam | Required | HD 1080p |
| OS | Windows 10+, Ubuntu 20.04+, Debian 11+ | Latest |

---

## 🔧 Features

- ⚡ Real-time face swap at 15-30 FPS (CPU only, no GPU needed)
- 🖱️ Drag & drop photo upload
- 👤 Face gallery — save multiple faces, switch instantly
- 🎭 Multi-face mode — swap specific people in group calls
- 🌫️ Background blur
- 🎛️ Performance modes: Speed / Balanced / Quality
- 💾 Preset profiles
- ⌨️ Hotkeys: `Space` toggle, `F1` cycle mode, `Esc` minimize
- 🔄 Auto performance tuner

---

## 📂 Project Structure

```
echelon/
├── main.py                 # Entry point
├── run.sh                  # Linux launcher (auto-sets up virtual camera)
├── ui/                     # PyQt6 UI (main window, face panel, onboarding)
├── core/                   # Face detection, pipeline, inference engine
├── config/                 # Settings management
├── assets/                 # Icons, stylesheets
├── models/                 # AI model downloader with mirror fallback
└── .github/workflows/      # CI/CD — auto-builds on every tag
```

---

*Built by Zero · [Releases](https://github.com/gengenesix/echelon/releases) · [Actions](https://github.com/gengenesix/echelon/actions)*
