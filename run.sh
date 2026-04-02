#!/bin/bash
# Echelon launcher — sets up virtual camera if needed, then starts the app

cd "$(dirname "$0")"

# ── Virtual camera setup (Linux only) ───────────────────────────────────────
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if ! lsmod | grep -q v4l2loopback 2>/dev/null; then
        echo "[echelon] Loading v4l2loopback kernel module..."
        if command -v modprobe &>/dev/null; then
            sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="Echelon Camera" exclusive_caps=1 2>/dev/null && \
                echo "[echelon] Virtual camera ready: /dev/video10" || \
                echo "[echelon] Warning: Could not load v4l2loopback. Run: sudo modprobe v4l2loopback devices=1 video_nr=10 card_label='Echelon Camera' exclusive_caps=1"
        fi
    else
        echo "[echelon] Virtual camera: already loaded"
    fi
fi

# ── Wayland/X11 display detection ────────────────────────────────────────────
if [[ -z "$DISPLAY" && -n "$WAYLAND_DISPLAY" ]]; then
    export QT_QPA_PLATFORM=wayland
elif [[ -z "$DISPLAY" && -z "$WAYLAND_DISPLAY" ]]; then
    export DISPLAY=:0
fi

# ── Launch app ────────────────────────────────────────────────────────────────
source venv/bin/activate
exec python3 main.py "$@"
