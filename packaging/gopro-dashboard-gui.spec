# -*- mode: python ; coding: utf-8 -*-
# Builds a portable, self-contained distribution of the GoPro dashboard render GUI:
# three .exe files (gopro-dashboard-gui, gopro-dashboard, gopro-join-list) sharing one
# dependency bundle, plus the layouts/profiles the GUI reads at runtime. ffmpeg itself is
# NOT bundled by this spec - packaging/build.ps1 copies it in afterward.
#
# Build with: pyinstaller packaging/gopro-dashboard-gui.spec --distpath dist --workpath build --clean

import pathlib
import sys

ROOT = pathlib.Path(SPECPATH).parent

datas = [
    (str(ROOT / "gopro_overlay" / "layouts"), "gopro_overlay/layouts"),
    (str(ROOT / "go_pro_graphics" / "ffmpeg-profiles.json"), "go_pro_graphics"),
]
binaries = []

# Windows/conda-only: this venv's Python is Anaconda-based there, and Tcl/Tk DLLs + script
# library live under conda's own Library\bin\ / Library\lib\ layout, which PyInstaller's
# built-in tkinter hook doesn't find automatically (unlike a standard python.org CPython
# install) - bundle them explicitly. sys.base_prefix resolves to the Anaconda install this venv
# was created from, regardless of which machine/user builds the package. On macOS/Linux, Python
# (conda or otherwise) uses the standard Unix lib/ layout that PyInstaller's tkinter hook already
# handles on its own, so none of this applies there.
if sys.platform == "win32":
    CONDA_HOME = pathlib.Path(sys.base_prefix)

    datas += [
        (str(CONDA_HOME / "Library" / "lib" / "tcl8.6"), "tcl8.6"),
        (str(CONDA_HOME / "Library" / "lib" / "tk8.6"), "tk8.6"),
    ]

    # Individually-bundled DLLs that this Anaconda-based venv's compiled stdlib extensions
    # (_tkinter, _sqlite3, _ctypes, ...) need at runtime but PyInstaller's hooks don't discover
    # automatically, since conda packages its native libs under Library\bin\ rather than the
    # standard CPython layout. Add more here if a frozen build reports another
    # "DLL load failed while importing _xxx" - bundling all of Library\bin\ (1.5GB) instead isn't
    # an option size-wise, so this stays a targeted list built up empirically.
    _CONDA_DLLS = ["tcl86t.dll", "tk86t.dll", "sqlite3.dll", "ffi-7.dll", "ffi-8.dll", "ffi.dll"]
    binaries += [(str(CONDA_HOME / "Library" / "bin" / name), ".") for name in _CONDA_DLLS
                 if (CONDA_HOME / "Library" / "bin" / name).exists()]

common_kwargs = dict(
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

a_gui = Analysis([str(ROOT / "bin" / "gopro-dashboard-gui.py")], **common_kwargs)
a_dashboard = Analysis([str(ROOT / "bin" / "gopro-dashboard.py")], **common_kwargs)
a_join = Analysis([str(ROOT / "bin" / "gopro-join-list.py")], **common_kwargs)

MERGE(
    (a_gui, "gopro-dashboard-gui", "gopro-dashboard-gui"),
    (a_dashboard, "gopro-dashboard", "gopro-dashboard"),
    (a_join, "gopro-join-list", "gopro-join-list"),
)

pyz_gui = PYZ(a_gui.pure, a_gui.zipped_data)
exe_gui = EXE(
    pyz_gui, a_gui.scripts, [], exclude_binaries=True,
    name="gopro-dashboard-gui", console=False, upx=False,
)

# console=False: these two are launched by the GUI as background workers (its subprocess
# calls already pass CREATE_NO_WINDOW too - this is belt-and-suspenders so no window appears
# no matter how they're invoked). Their stdout/stderr are still fully readable via
# subprocess.PIPE either way - console=False only affects whether they allocate their own OS
# console window when run standalone, not whether a parent process can redirect their output.
pyz_dashboard = PYZ(a_dashboard.pure, a_dashboard.zipped_data)
exe_dashboard = EXE(
    pyz_dashboard, a_dashboard.scripts, [], exclude_binaries=True,
    name="gopro-dashboard", console=False, upx=False,
)

pyz_join = PYZ(a_join.pure, a_join.zipped_data)
exe_join = EXE(
    pyz_join, a_join.scripts, [], exclude_binaries=True,
    name="gopro-join-list", console=False, upx=False,
)

coll = COLLECT(
    exe_gui, a_gui.binaries, a_gui.zipfiles, a_gui.datas,
    exe_dashboard, a_dashboard.binaries, a_dashboard.zipfiles, a_dashboard.datas,
    exe_join, a_join.binaries, a_join.zipfiles, a_join.datas,
    strip=False, upx=False, name="Domestique",
)
