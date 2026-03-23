#!/bin/bash
set -e

APP_NAME="echelon"
VERSION="2.0.0"
PKG_DIR="${APP_NAME}_${VERSION}_amd64"

# Create deb structure
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/opt/echelon"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$PKG_DIR/usr/local/bin"

# Control file
cat > "$PKG_DIR/DEBIAN/control" << EOF
Package: echelon
Version: $VERSION
Section: video
Priority: optional
Architecture: amd64
Depends: v4l2loopback-dkms, libgl1, libglib2.0-0
Maintainer: Zero <zero@echelon.app>
Description: Real-time face swap for video calls
 Echelon swaps your face in real-time for any video call app.
 Works with Zoom, WhatsApp, Google Meet, Discord, and Teams.
 Created by Zero.
EOF

# Post-install script
cat > "$PKG_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
modprobe v4l2loopback devices=1 video_nr=10 card_label="Echelon Camera" exclusive_caps=1 2>/dev/null || true
echo "v4l2loopback" > /etc/modules-load.d/v4l2loopback.conf 2>/dev/null || true
echo 'options v4l2loopback devices=1 video_nr=10 card_label="Echelon Camera" exclusive_caps=1' > /etc/modprobe.d/v4l2loopback.conf 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
echo "✅ Echelon installed. Launch from app menu or run: echelon"
EOF
chmod 755 "$PKG_DIR/DEBIAN/postinst"

# Copy binary
cp -r dist/Echelon/* "$PKG_DIR/opt/echelon/"

# Create launcher symlink script
cat > "$PKG_DIR/usr/local/bin/echelon" << 'EOF'
#!/bin/bash
cd /opt/echelon
./Echelon "$@"
EOF
chmod 755 "$PKG_DIR/usr/local/bin/echelon"

# Copy desktop file and icon
cp echelon.desktop "$PKG_DIR/usr/share/applications/"
sed -i 's|Exec=Echelon|Exec=/opt/echelon/Echelon|' "$PKG_DIR/usr/share/applications/echelon.desktop"
sed -i 's|Icon=echelon_logo|Icon=/opt/echelon/assets/icons/icon_256.png|' "$PKG_DIR/usr/share/applications/echelon.desktop"
cp assets/icons/icon_256.png "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/echelon_logo.png"

# Build deb
dpkg-deb --build "$PKG_DIR"
echo "✅ Deb package created: ${PKG_DIR}.deb"
