# Echelon — Android Build Notes

## Why PyQt6 Does Not Work on Android

PyQt6 is a desktop GUI framework built on Qt6. Qt6 does **not** support Android as a target for Python applications via PyQt6. Attempting to run PyQt6 code on Android will fail — there is no supported path.

## Android Build Targets

To bring Echelon to Android, a separate build is required using one of:

### Option 1: BeeWare (Briefcase) — Recommended

BeeWare's [Briefcase](https://briefcase.readthedocs.io/) can package Python apps for Android.
The UI layer must be rewritten using [Toga](https://toga.readthedocs.io/) (BeeWare's cross-platform widget toolkit).

**Setup:**
```bash
pip install briefcase toga
briefcase create android
briefcase build android
briefcase run android
```

**Notes:**
- Toga widgets map to native Android views
- The face swap core (ONNX inference) can be reused — onnxruntime has Android builds
- Camera access requires Toga's camera API or OpenCV for Android
- Virtual camera output is not available on Android — output would go to in-app preview only

### Option 2: Kivy

[Kivy](https://kivy.org/) supports Android via [python-for-android](https://python-for-android.readthedocs.io/).

```bash
pip install kivy buildozer
# Edit buildozer.spec with requirements
buildozer android debug deploy run
```

**Notes:**
- Kivy has its own UI paradigm (no native widgets)
- More mature Android toolchain than Briefcase
- onnxruntime-mobile is the target package for inference

## Shared Core

The following core modules can be reused across platforms with minimal changes:
- `core/inference.py` — ONNX face swap (use `onnxruntime-mobile`)
- `core/face_detector.py` — InsightFace detection
- `core/face_gallery.py` — face persistence
- `config/manager.py` — configuration

## Current Status

No Android build exists. This is a future work item. The desktop (Linux/macOS/Windows) build via PyQt6 remains the primary target.
