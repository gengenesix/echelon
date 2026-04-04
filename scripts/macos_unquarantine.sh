#!/bin/bash
# Echelon macOS Quarantine Bypass
# Run this once after downloading if macOS blocks the app
echo "Removing macOS quarantine from Echelon..."
xattr -rd com.apple.quarantine /Applications/Echelon.app 2>/dev/null || \
xattr -rd com.apple.quarantine "$HOME/Downloads/Echelon.app" 2>/dev/null || true
chmod +x /Applications/Echelon.app/Contents/MacOS/Echelon 2>/dev/null || true
echo "✅ Done. Launch Echelon normally from Applications."
