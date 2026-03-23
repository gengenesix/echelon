# Building Echelon — Developer Guide

## Quick Answer: Where are the installer files?

→ **[github.com/gengenesix/echelon/releases](https://github.com/gengenesix/echelon/releases)**

After every successful build, the following files appear there automatically:
- `Echelon-Setup.exe` — Windows installer
- `Echelon-x86_64.AppImage` — Linux (any distro)
- `echelon_2.0.0_amd64.deb` — Ubuntu/Debian package

---

## How Builds Work

Builds run on **GitHub Actions** — free cloud servers provided by GitHub.

| Platform | Server Used | Output File |
|---|---|---|
| Windows | `windows-latest` (real Windows Server) | `Echelon-Setup.exe` |
| Linux | `ubuntu-22.04` (real Ubuntu server) | `Echelon-x86_64.AppImage` + `.deb` |

The build pipeline is defined in `.github/workflows/build.yml`.

---

## Triggering a Build

### Method 1 — Push a version tag (releases to public)
```bash
git tag -a v2.1.0 -m "Echelon v2.1.0"
git push origin v2.1.0
```
This builds AND publishes a GitHub Release with download links.

### Method 2 — Manual trigger (for testing, no public release)
1. Go to: https://github.com/gengenesix/echelon/actions/workflows/build.yml
2. Click **"Run workflow"** button (top right)
3. Click the green **"Run workflow"** button
4. Wait ~25 minutes
5. Download built files from the **Artifacts** section of the run

---

## What the Build Does (Step by Step)

### Windows build:
1. Spins up a Windows Server machine
2. Installs Python 3.11
3. Installs all Python dependencies (PyQt6, OpenCV, ONNX, InsightFace, etc.)
4. Runs PyInstaller — bundles everything into `dist/Echelon/`
5. Runs NSIS — wraps the bundle into `Echelon-Setup.exe`
6. Uploads as a build artifact

### Linux build:
1. Spins up Ubuntu 22.04
2. Installs Python 3.11 + system libs
3. Installs all Python dependencies
4. Runs PyInstaller — bundles into `dist/Echelon/`
5. Packages as AppImage (self-contained, runs anywhere)
6. Packages as .deb (for traditional install)
7. Uploads both as artifacts

---

## Offline / USB Verification

All builds bundle:
- ✅ Python runtime (no Python needed on target)
- ✅ All Python packages (PyQt6, OpenCV, ONNX Runtime, InsightFace, etc.)
- ✅ All shared libraries
- ✅ App icon, stylesheet, UI assets

**Not bundled (downloaded on first launch):**
- AI models (`inswapper_128.onnx` ~554MB, `buffalo_l` ~300MB)
- These are downloaded automatically on first run (one-time, ~850MB)
- After download, app works fully offline

To make a 100% offline build (pre-bundle models):
```bash
# Download models to your dev machine first:
python3 -c "from models.downloader import ModelDownloader; ModelDownloader().download_all()"

# Then add to the spec:
# datas=[('models/models', 'models/models')]
```

---

## Local Build (on your own machine)

### Linux
```bash
cd ~/xeroclaw/echelon
source venv/bin/activate
pip install pyinstaller
pyinstaller echelon.spec --clean --noconfirm
bash package_appimage.sh    # builds AppImage
bash package_deb.sh         # builds .deb
```

### Windows
```cmd
cd echelon
pip install pyinstaller
python package_windows.py
makensis installer.nsi
```

---

## Build Artifacts Location

After a GitHub Actions run:
1. Go to the run page (linked in Actions tab)
2. Scroll to **Artifacts** section at the bottom
3. Download `Echelon-Windows` or `Echelon-Linux`

After a tagged release:
- All files are at: https://github.com/gengenesix/echelon/releases

---

## Troubleshooting Builds

**Windows build fails with "module not found":**
Add the missing module to `--hidden-import=` in the build.yml workflow.

**Linux AppImage won't run:**
```bash
chmod +x Echelon-x86_64.AppImage
# If FUSE error: install libfuse2
sudo apt install libfuse2
```

**Models don't download on first launch:**
Check internet connection. Models are hosted on HuggingFace.
After first download, all subsequent launches work offline.
