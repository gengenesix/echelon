#!/bin/bash
set -e

APP_NAME="Echelon"
APP_DIR="$APP_NAME.AppDir"

# Create AppDir structure
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APP_DIR/usr/share/applications"

# Copy PyInstaller output
cp -r dist/Echelon/* "$APP_DIR/usr/bin/"

# Copy icon
cp assets/icons/icon_256.png "$APP_DIR/usr/share/icons/hicolor/256x256/apps/echelon_logo.png"
cp assets/icons/icon_256.png "$APP_DIR/echelon_logo.png"

# Copy desktop file
cp echelon.desktop "$APP_DIR/"
cp echelon.desktop "$APP_DIR/usr/share/applications/"

# Create AppRun
cat > "$APP_DIR/AppRun" << 'APPRUN'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/Echelon" "$@"
APPRUN
chmod +x "$APP_DIR/AppRun"

# Download appimagetool if not present
if [ ! -f appimagetool-x86_64.AppImage ]; then
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool-x86_64.AppImage
fi

# Build AppImage
ARCH=x86_64 ./appimagetool-x86_64.AppImage "$APP_DIR" "${APP_NAME}-x86_64.AppImage"
echo "✅ AppImage created: ${APP_NAME}-x86_64.AppImage"
