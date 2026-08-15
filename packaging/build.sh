#!/usr/bin/env bash
# ==============================
# Build a portable, self-contained distribution of Domestique (the GoPro dashboard render GUI)
# for macOS/Linux - the build.ps1 equivalent for non-Windows.
#
# Produces dist/Domestique/ containing:
#   - gopro-dashboard-gui, gopro-dashboard, gopro-join-list (+ shared _internal/)
#   - ffmpeg/bin/ffmpeg, ffprobe (copied from PATH, or $FFMPEG_DIR if set)
#   - go_pro_graphics/ffmpeg-profiles.json, gopro_overlay/layouts/*.xml (via the spec's datas)
# and zips it to dist/Domestique-portable.zip.
#
# Written and code-reviewed on Windows, not yet run on an actual Mac - the Windows/conda-specific
# Tcl/Tk bundling in gopro-dashboard-gui.spec is already guarded to skip on this platform, but
# please report any PyInstaller/tkinter hook surprises you hit running this for real.
# ==============================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$REPO_DIR/.venv/bin/python"
SPEC="$REPO_DIR/packaging/gopro-dashboard-gui.spec"
DIST_DIR="$REPO_DIR/dist"
BUILD_DIR="$REPO_DIR/build"

# ffmpeg source: override with `FFMPEG_DIR=/path/to/bin ./build.sh`, otherwise auto-detect from
# PATH (e.g. Homebrew's /opt/homebrew/bin on Apple Silicon, /usr/local/bin on Intel).
if [ -n "${FFMPEG_DIR:-}" ]; then
    SOURCE_FFMPEG_DIR="$FFMPEG_DIR"
else
    FFMPEG_BIN="$(command -v ffmpeg || true)"
    if [ -z "$FFMPEG_BIN" ]; then
        echo "ffmpeg not found on PATH. Install it (e.g. 'brew install ffmpeg') or set FFMPEG_DIR." >&2
        exit 1
    fi
    SOURCE_FFMPEG_DIR="$(dirname "$FFMPEG_BIN")"
fi

cd "$REPO_DIR"

if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "Installing PyInstaller..."
    "$PYTHON" -m pip install pyinstaller
fi

echo "Building executables..."
"$PYTHON" -m PyInstaller "$SPEC" --distpath "$DIST_DIR" --workpath "$BUILD_DIR" --clean --noconfirm

OUT_DIR="$DIST_DIR/Domestique"

echo "Bundling ffmpeg..."
FFMPEG_OUT_DIR="$OUT_DIR/ffmpeg/bin"
mkdir -p "$FFMPEG_OUT_DIR"
cp "$SOURCE_FFMPEG_DIR/ffmpeg" "$FFMPEG_OUT_DIR/"
cp "$SOURCE_FFMPEG_DIR/ffprobe" "$FFMPEG_OUT_DIR/"

echo "Zipping..."
ZIP_PATH="$DIST_DIR/Domestique-portable.zip"
rm -f "$ZIP_PATH"
(cd "$DIST_DIR" && zip -r -q "$(basename "$ZIP_PATH")" "$(basename "$OUT_DIR")")

echo "Done: $ZIP_PATH"
