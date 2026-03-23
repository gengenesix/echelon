#!/bin/bash
set -e

echo "=== Building Echelon AppImage ==="

# Download appimagetool
if [ ! -f appimagetool-x86_64.AppImage ]; then
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool-x86_64.AppImage
fi

# Create AppDir
rm -rf Echelon.AppDir
mkdir -p Echelon.AppDir/usr/bin
mkdir -p Echelon.AppDir/usr/share/icons/hicolor/256x256/apps
mkdir -p Echelon.AppDir/usr/share/applications

# Copy PyInstaller output
cp -r dist/Echelon/* Echelon.AppDir/usr/bin/

# AppRun
cat > Echelon.AppDir/AppRun << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${HERE}/usr/lib:${LD_LIBRARY_PATH}"
export ALBUMENTATIONS_DISABLE_VERSION_CHECK=1
export NO_ALBUMENTATIONS_UPDATE=1
export MPLBACKEND=Agg
export MPLCONFIGDIR="${HOME}/.cache/matplotlib"
exec "${HERE}/usr/bin/Echelon" "$@"
EOF
chmod +x Echelon.AppDir/AppRun

# Icon
cp assets/icons/icon_256.png Echelon.AppDir/echelon.png
cp assets/icons/icon_256.png Echelon.AppDir/usr/share/icons/hicolor/256x256/apps/echelon.png

# Desktop file
cat > Echelon.AppDir/echelon.desktop << 'EOF'
[Desktop Entry]
Name=Echelon
Comment=Real-time face swap for video calls — by Zero
Exec=Echelon
Icon=echelon
Terminal=false
Type=Application
Categories=Video;AudioVideo;
EOF
cp Echelon.AppDir/echelon.desktop Echelon.AppDir/usr/share/applications/

# Build AppImage
ARCH=x86_64 ./appimagetool-x86_64.AppImage Echelon.AppDir Echelon-x86_64.AppImage
chmod +x Echelon-x86_64.AppImage
echo "AppImage built: $(du -sh Echelon-x86_64.AppImage)"
