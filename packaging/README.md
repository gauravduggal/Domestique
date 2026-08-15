# Building and running the Domestique app

This produces a portable, self-contained build of the Domestique GUI - no Python
install required to run it. The built app itself is never committed to git (see
`.gitignore`); only these build scripts and the `.spec` file are tracked. Regenerate
the app locally whenever you need it.

## Prerequisites

- The dev virtualenv set up and dependencies installed (`.venv/` at the repo root).
- `ffmpeg`/`ffprobe` available:
  - **Windows**: at `C:\ffmpeg\bin` (or edit `$SourceFfmpegDir` in `build.ps1`).
  - **macOS/Linux**: on `PATH` (e.g. `brew install ffmpeg`), or point at a specific
    copy with `FFMPEG_DIR=/path/to/bin`.
- PyInstaller isn't required up front - the build script installs it into the venv
  automatically on first run if it's missing.

## 1. Generate the package

**Windows** (PowerShell):
```powershell
.\packaging\build.ps1
```

**macOS/Linux**:
```bash
./packaging/build.sh
# or, to point at a specific ffmpeg install:
FFMPEG_DIR=/opt/homebrew/bin ./packaging/build.sh
```

Both produce:
- `dist/Domestique/` - the unpacked app (`gopro-dashboard-gui`, `gopro-dashboard`,
  `gopro-join-list`, bundled `ffmpeg`/`ffprobe`, layouts, and encoder profiles)
- `dist/Domestique-portable.zip` - the same thing, zipped up for handing to
  another machine

> The macOS path (`build.sh` + the `.spec`'s platform guards) hasn't been run on an
> actual Mac yet - it's a careful port from the working Windows build, not a
> verified one. Report any issues you hit.

## 2. Run it

Unzip `Domestique-portable.zip` anywhere (or just use `dist/Domestique/` directly
after step 1) and launch the GUI:

- **Windows**: double-click `gopro-dashboard-gui.exe`.
- **macOS/Linux**: `./gopro-dashboard-gui` from a terminal in that folder (`chmod +x`
  it first if needed). On macOS, since the app isn't code-signed, the first launch
  may need a right-click → Open (or clear the quarantine flag on a downloaded zip
  with `xattr -d com.apple.quarantine Domestique-portable.zip`) to get past
  Gatekeeper.

In the GUI: pick your GoPro clip(s), a FIT/GPX ride file, a profile (`av1_nvenc_*`
for an NVIDIA GPU, `av1_cpudec_cpuenc*` for CPU-only), a quality/speed preset, and
hit **Start Render**.
