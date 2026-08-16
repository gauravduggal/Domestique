#!/usr/bin/env bash
# ==============================
# Install the built Domestique app (see build.sh) to a chosen location on macOS/Linux.
# Extracts dist/Domestique-portable.zip and makes the bundled executables runnable.
#
# Usage: ./packaging/install.sh [destination-dir]
#   destination-dir defaults to ~/Applications
# ==============================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZIP_PATH="$REPO_DIR/dist/Domestique-portable.zip"
DEST_DIR="${1:-$HOME/Applications}"

if [ ! -f "$ZIP_PATH" ]; then
    echo "$ZIP_PATH not found - run ./packaging/build.sh first." >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
echo "Extracting to $DEST_DIR..."
unzip -o -q "$ZIP_PATH" -d "$DEST_DIR"

APP_DIR="$DEST_DIR/Domestique"

# The zip is built on the same platform it's installed on in the typical case, so the
# executable bit usually survives unzip already - chmod defensively in case it doesn't
# (e.g. a zip transferred through a tool that drops Unix permissions).
for exe in gopro-dashboard-gui gopro-dashboard gopro-join-list; do
    if [ -f "$APP_DIR/$exe" ]; then
        chmod +x "$APP_DIR/$exe"
    fi
done

echo "Installed to: $APP_DIR"
echo "Run it with: $APP_DIR/gopro-dashboard-gui"
if [ "$(uname)" = "Darwin" ]; then
    echo "(First launch may need right-click -> Open instead, to get past Gatekeeper since the app isn't code-signed.)"
fi
