#!/usr/bin/env python3

import os
import pathlib
import sys

# This venv's Python is Anaconda-based: its Tcl/Tk DLLs and script library live under conda's
# own Library\bin\ / Library\lib\ layout, not the standard CPython locations PyInstaller's
# tkinter hook expects to find automatically - point Tcl/Tk at the bundled copy (see
# packaging/gopro-dashboard-gui.spec) explicitly, before importing tkinter, so a frozen build
# doesn't fail with "DLL load failed while importing _tkinter". Windows/conda-specific: on macOS
# (python.org/Homebrew Python, not conda) PyInstaller's own tkinter hook bundles Tcl/Tk correctly
# without this, and pointing TCL_LIBRARY/TK_LIBRARY at a nonexistent _internal/tcl8.6 there would
# break Tk instead of fixing it.
if getattr(sys, "frozen", False) and sys.platform == "win32":
    _internal_dir = pathlib.Path(sys.executable).resolve().parent / "_internal"
    os.environ.setdefault("TCL_LIBRARY", str(_internal_dir / "tcl8.6"))
    os.environ.setdefault("TK_LIBRARY", str(_internal_dir / "tk8.6"))

import json
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from gopro_overlay.ffmpeg_profile import builtin_profiles as BUILTIN_PROFILES

GPU_CODEC_HINTS = ("nvenc", "qsv", "vaapi", "videotoolbox", "amf")

# When this GUI is frozen (console=False), it has no console of its own - spawning a console
# subprocess (nvidia-smi, powershell, the join/render .exe's) would otherwise make Windows pop
# up a new console window for it, flashing on screen every ~1.5s during stats polling. Suppress
# that on every subprocess call below.
NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# Suggested -cq (NVENC) / -crf (SVT-AV1) values per quality tier. Same 0-63 scale/direction on
# both encoders, but NVENC's RDO is weaker than SVT-AV1's at the same nominal number, so it
# gets slightly lower (= higher quality target) suggestions to land at comparable visual quality.
QUALITY_SUGGESTIONS_GPU = {"Low": 40, "Medium": 28, "High": 18}
QUALITY_SUGGESTIONS_CPU = {"Low": 36, "Medium": 24, "High": 16}

# Suggested -preset values per speed tier. NVENC's pN scale runs fastest(p1)->slowest/best(p7);
# SVT-AV1's scale is inverted, slowest/best(0)->fastest(13) - so "Slow" and "Fast" map to
# opposite ends of the raw number on each encoder, which is why this is a separate table
# rather than reusing GPU_CODEC_HINTS-style shared logic.
PRESET_SUGGESTIONS_GPU = {"Fast": "p2", "Balanced": "p5", "Slow": "p7"}
PRESET_SUGGESTIONS_CPU = {"Fast": "10", "Balanced": "6", "Slow": "2"}

# Two ways this script runs:
#  - dev: via the venv's python.exe, from either bin/ (source) or .venv/Scripts/ (the
#    installed console-script copy, one directory deeper) - REPO_DIR is derived from
#    sys.executable (the venv python.exe location), not __file__, since __file__ silently
#    points at the wrong repo root depending on which copy was launched.
#  - frozen: bundled into a standalone .exe via PyInstaller (see packaging/) for distribution
#    to a machine with no Python/venv/ffmpeg installed at all - resources live alongside the
#    .exe itself instead of in a dev checkout.
FROZEN = getattr(sys, "frozen", False)

# PyInstaller names frozen executables with a .exe suffix on Windows only.
_EXE_SUFFIX = ".exe" if sys.platform == "win32" else ""

if FROZEN:
    APP_DIR = pathlib.Path(sys.executable).resolve().parent
    # PyInstaller's onedir layout puts collected `datas` inside _internal/, not beside the
    # .exe itself - only the sibling .exe files and our manually-copied ffmpeg/ live at APP_DIR.
    INTERNAL_DIR = APP_DIR / "_internal"
    JOIN_CMD_BASE = [str(APP_DIR / f"gopro-join-list{_EXE_SUFFIX}")]
    DASHBOARD_CMD_BASE = [str(APP_DIR / f"gopro-dashboard{_EXE_SUFFIX}")]
    CONFIG_DIR = INTERNAL_DIR / "go_pro_graphics"
    LAYOUTS_DIR = INTERNAL_DIR / "gopro_overlay" / "layouts"
    DEFAULT_FFMPEG_DIR = APP_DIR / "ffmpeg" / "bin"
    WORKING_DIR = APP_DIR
else:
    # venv layout differs by platform: Windows uses <venv>/Scripts/python.exe, POSIX
    # (macOS/Linux) uses <venv>/bin/python - both are one directory below the venv root, so the
    # REPO_DIR derivation (three parents up from the interpreter) holds on either platform.
    _VENV_SUBDIR = "Scripts" if sys.platform == "win32" else "bin"
    _PYTHON_NAME = f"python{_EXE_SUFFIX}"
    REPO_DIR = pathlib.Path(sys.executable).resolve().parent.parent.parent
    VENV_PYTHON = REPO_DIR / ".venv" / _VENV_SUBDIR / "python.exe" if sys.platform == "win32" else REPO_DIR / ".venv" / _VENV_SUBDIR / _PYTHON_NAME
    JOIN_CMD_BASE = [str(VENV_PYTHON), str(REPO_DIR / ".venv" / _VENV_SUBDIR / "gopro-join-list.py")]
    DASHBOARD_CMD_BASE = [str(VENV_PYTHON), str(REPO_DIR / ".venv" / _VENV_SUBDIR / "gopro-dashboard.py")]
    CONFIG_DIR = REPO_DIR / "go_pro_graphics"
    LAYOUTS_DIR = REPO_DIR / "gopro_overlay" / "layouts"
    if sys.platform == "win32":
        DEFAULT_FFMPEG_DIR = pathlib.Path(r"C:\ffmpeg\bin")
    else:
        # macOS/Linux: ffmpeg is typically already on PATH (e.g. installed via Homebrew) -
        # None means the CLI's own "--ffmpeg-dir" default (look in PATH) is used instead.
        _ffmpeg_on_path = shutil.which("ffmpeg")
        DEFAULT_FFMPEG_DIR = pathlib.Path(_ffmpeg_on_path).parent if _ffmpeg_on_path else None
    WORKING_DIR = REPO_DIR

def _ffmpeg_dir_args():
    # DEFAULT_FFMPEG_DIR is None on macOS/Linux dev mode when ffmpeg isn't found on PATH -
    # omit the flag entirely so the CLI falls back to its own "look in PATH" default instead
    # of being passed a literal "None".
    return ["--ffmpeg-dir", str(DEFAULT_FFMPEG_DIR)] if DEFAULT_FFMPEG_DIR else []


PROFILES_FILE = CONFIG_DIR / "ffmpeg-profiles.json"
# Helvetica.ttc has shipped in every macOS release; Arial isn't guaranteed to be present.
DEFAULT_FONT = pathlib.Path(r"C:\Windows\Fonts\arial.ttf") if sys.platform == "win32" \
    else pathlib.Path("/System/Library/Fonts/Helvetica.ttc")

PROGRESS_RE = re.compile(r"Render:\s*[\d,]+\s*\[\s*(\d+)%\]\s*\[\s*([\d.]+)/s\]\s*\|.*?\|\s*ETA:\s*(\S+)")


def load_profiles():
    names = []
    if PROFILES_FILE.exists():
        try:
            names = list(json.loads(PROFILES_FILE.read_text()).keys())
        except (json.JSONDecodeError, OSError):
            pass
    if "av1_nvenc_5k" not in names:
        names.insert(0, "av1_nvenc_5k")
    return names


# Only the layouts actually used by this GUI's 4 profiles (2 resolutions x GPU/CPU) - the
# layouts dir also ships ~13 unrelated bundled layouts (other resolutions, motorbike styles,
# examples) that aren't relevant here and would just clutter the dropdown.
KNOWN_LAYOUTS = ("default-5312x2988.xml", "default-1280x720.xml")


def load_layouts():
    if not LAYOUTS_DIR.exists():
        return list(KNOWN_LAYOUTS)
    available = {p.name for p in LAYOUTS_DIR.glob("*.xml")}
    return [name for name in KNOWN_LAYOUTS if name in available]


def load_all_profile_specs():
    """Builtin + user-defined profile definitions, for GPU/CPU detection (not the dropdown list)."""
    specs = dict(BUILTIN_PROFILES)
    if PROFILES_FILE.exists():
        try:
            specs.update(json.loads(PROFILES_FILE.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return specs


def is_gpu_profile(name, specs):
    output = " ".join(specs.get(name, {}).get("output", [])).lower()
    return any(hint in output for hint in GPU_CODEC_HINTS)


def nvidia_gpu_available():
    try:
        return subprocess.run(["nvidia-smi"], capture_output=True, timeout=2,
                               creationflags=NO_WINDOW_FLAGS).returncode == 0
    except Exception:
        return False


def extract_flag_value(output_args, flag, default=""):
    if flag in output_args:
        idx = output_args.index(flag)
        if idx + 1 < len(output_args):
            return output_args[idx + 1]
    return default


def override_output_args(output_args, overrides):
    args = list(output_args)
    for flag, value in overrides.items():
        if flag in args:
            idx = args.index(flag)
            if idx + 1 < len(args):
                args[idx + 1] = str(value)
                continue
        args.extend([flag, str(value)])
    return args


class RenderJob:
    """Runs join+render in a background thread, emits events onto a queue."""

    def __init__(self, clips, ride_file, output_file, profile, layout, quality, preset,
                 overlay_size, profile_specs, events):
        self.clips = clips
        self.ride_file = ride_file
        self.output_file = output_file
        self.profile = profile
        self.layout = layout
        self.quality = quality
        self.preset = preset
        self.overlay_size = overlay_size
        self.profile_specs = profile_specs
        self.events = events
        self._proc = None

    def cancel(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def run(self):
        try:
            joined_path = self.output_file.with_name(self.output_file.stem + "_joined_tmp.mp4")

            self.events.put(("stage", f"Joining {len(self.clips)} clips..."))
            self.events.put(("indeterminate", None))
            code, tail = self._run_join(joined_path)
            if code != 0:
                self.events.put(("error", "Join failed:\n" + "\n".join(tail)))
                return

            self.events.put(("stage", "Rendering overlay..."))
            self.events.put(("determinate", None))
            code, tail = self._run_render(joined_path)
            if code != 0:
                self.events.put(("error", "Render failed:\n" + "\n".join(tail)))
                return

            self.events.put(("stage", "Complete"))
            self.events.put(("progress", 100, "--", "0:00:00"))
            self.events.put(("done", str(self.output_file)))
        except Exception as e:
            self.events.put(("error", f"Unexpected error: {e}"))

    def _run_join(self, joined_path):
        cmd = JOIN_CMD_BASE + _ffmpeg_dir_args() + \
              [str(joined_path), *[str(c) for c in self.clips]]
        return self._stream(cmd, parse_progress=False)

    def _run_render(self, joined_path):
        fit_flag = "--gpx" if self.ride_file.suffix.lower() == ".gpx" else "--fit"

        temp_config_dir = tempfile.mkdtemp(prefix="gopro_gui_profile_")
        try:
            spec = self.profile_specs.get(self.profile, {})
            quality_flag = "-cq" if is_gpu_profile(self.profile, self.profile_specs) else "-crf"
            overridden_output = override_output_args(
                spec.get("output", []),
                {quality_flag: str(self.quality), "-preset": str(self.preset)},
            )
            overridden_spec = {"input": spec.get("input", []), "output": overridden_output}
            if "filter" in spec:
                overridden_spec["filter"] = spec["filter"]
            (pathlib.Path(temp_config_dir) / "ffmpeg-profiles.json").write_text(
                json.dumps({self.profile: overridden_spec})
            )

            cmd = DASHBOARD_CMD_BASE + _ffmpeg_dir_args() + [
                   "--config-dir", temp_config_dir,
                   "--font", str(DEFAULT_FONT),
                   "--layout-xml", str(LAYOUTS_DIR / self.layout),
                   "--profile", self.profile]
            if self.overlay_size:
                cmd += ["--overlay-size", self.overlay_size]
            cmd += [fit_flag, str(self.ride_file),
                    "--gpx-merge", "OVERWRITE",
                    str(joined_path), str(self.output_file)]
            return self._stream(cmd, parse_progress=True)
        finally:
            shutil.rmtree(temp_config_dir, ignore_errors=True)

    def _stream(self, cmd, parse_progress):
        tail = []
        self._proc = subprocess.Popen(
            cmd, cwd=str(WORKING_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0, creationflags=NO_WINDOW_FLAGS,
        )
        buf = b""
        while True:
            chunk = self._proc.stdout.read(256)
            if not chunk:
                break
            buf += chunk
            *complete, buf = re.split(rb"[\r\n]", buf)
            for raw in complete:
                line = raw.decode(errors="replace").strip()
                if not line:
                    continue
                tail.append(line)
                del tail[:-20]
                if parse_progress:
                    m = PROGRESS_RE.search(line)
                    if m:
                        self.events.put(("progress", int(m.group(1)), m.group(2), m.group(3)))
        self._proc.wait()
        return self._proc.returncode, tail


class App:
    def __init__(self, root):
        self.root = root
        root.title("Domestique")

        self.clips = []
        self.ride_file = None
        self.output_file = None
        self.job = None
        self.events = queue.Queue()

        pad = {"padx": 8, "pady": 4}

        frm = ttk.Frame(root)
        frm.grid(row=0, column=0, sticky="nsew", **pad)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="GoPro Video Files:").grid(row=0, column=0, sticky="w")
        self.clips_var = tk.StringVar(value="No files selected")
        ttk.Entry(frm, textvariable=self.clips_var, state="readonly", width=60).grid(row=0, column=1, sticky="ew")
        ttk.Button(frm, text="Browse...", command=self.browse_clips).grid(row=0, column=2)

        self.clips_list = tk.Listbox(frm, height=5)
        self.clips_list.grid(row=1, column=0, columnspan=3, sticky="ew", **pad)

        ttk.Label(frm, text="Ride Data File (FIT/GPX):").grid(row=2, column=0, sticky="w")
        self.ride_var = tk.StringVar(value="No file selected")
        ttk.Entry(frm, textvariable=self.ride_var, state="readonly", width=60).grid(row=2, column=1, sticky="ew")
        ttk.Button(frm, text="Browse...", command=self.browse_ride).grid(row=2, column=2)

        ttk.Label(frm, text="Output File:").grid(row=3, column=0, sticky="w")
        self.output_var = tk.StringVar(value="")
        self.output_var.trace_add("write", lambda *_: self.update_start_state())
        ttk.Entry(frm, textvariable=self.output_var, width=60).grid(row=3, column=1, sticky="ew")
        ttk.Button(frm, text="Browse...", command=self.browse_output).grid(row=3, column=2)

        self.layouts = load_layouts()

        ttk.Label(frm, text="Profile:").grid(row=4, column=0, sticky="w")
        profiles = load_profiles()
        self.profile_specs = load_all_profile_specs()
        self.gpu_available = nvidia_gpu_available()
        default_profile = next(
            (p for p in profiles if is_gpu_profile(p, self.profile_specs) == self.gpu_available),
            profiles[0],
        )
        self.profile_var = tk.StringVar(value=default_profile)
        self.current_profile = self.profile_var.get()
        self.profile_var.trace_add("write", lambda *_: self.on_profile_change())
        ttk.Combobox(frm, textvariable=self.profile_var, values=profiles, state="readonly").grid(row=4, column=1, sticky="w")
        gpu_status_text = ("NVIDIA GPU detected — defaulting to GPU encoding" if self.gpu_available
                            else "No NVIDIA GPU detected — defaulting to CPU encoding")
        ttk.Label(frm, text=gpu_status_text, foreground="gray").grid(row=4, column=2, sticky="w")

        ttk.Label(frm, text="Layout:").grid(row=5, column=0, sticky="w")
        default_layout = "default-5312x2988.xml" if "default-5312x2988.xml" in self.layouts else (self.layouts[0] if self.layouts else "")
        self.layout_var = tk.StringVar(value=default_layout)
        ttk.Combobox(frm, textvariable=self.layout_var, values=self.layouts, state="readonly").grid(row=5, column=1, sticky="w")

        ttk.Label(frm, text="Quality (CRF/CQ):").grid(row=6, column=0, sticky="w")
        self.quality_var = tk.IntVar(value=0)
        ttk.Spinbox(frm, from_=0, to=63, textvariable=self.quality_var, width=6).grid(row=6, column=1, sticky="w")

        quality_presets = ttk.Frame(frm)
        quality_presets.grid(row=6, column=2, sticky="w")
        self.quality_preset_buttons = {}
        for level in ("Low", "Medium", "High"):
            btn = ttk.Button(quality_presets, command=lambda lv=level: self.set_quality_preset(lv))
            btn.pack(side="left", padx=(0, 4))
            self.quality_preset_buttons[level] = btn

        ttk.Label(frm, text="Speed Preset:").grid(row=7, column=0, sticky="w")
        self.preset_var = tk.StringVar(value="")
        self.preset_combo = ttk.Combobox(frm, textvariable=self.preset_var, state="readonly")
        self.preset_combo.grid(row=7, column=1, sticky="w")

        preset_presets = ttk.Frame(frm)
        preset_presets.grid(row=7, column=2, sticky="w")
        self.preset_preset_buttons = {}
        for level in ("Fast", "Balanced", "Slow"):
            btn = ttk.Button(preset_presets, command=lambda lv=level: self.set_speed_preset(lv))
            btn.pack(side="left", padx=(0, 4))
            self.preset_preset_buttons[level] = btn

        self.on_profile_change()  # seed Quality/Preset/Layout from the initial profile selection

        self.start_btn = ttk.Button(frm, text="Start Render", command=self.start, state="disabled")
        self.start_btn.grid(row=8, column=0, columnspan=3, pady=8)

        status = ttk.LabelFrame(frm, text="Status")
        status.grid(row=9, column=0, columnspan=3, sticky="ew", pady=8)
        status.columnconfigure(0, weight=1)

        self.stage_var = tk.StringVar(value="Idle")
        ttk.Label(status, textvariable=self.stage_var).grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        self.progress = ttk.Progressbar(status, mode="determinate", length=340)
        self.progress.grid(row=1, column=0, sticky="ew", **pad)

        self.fps_var = tk.StringVar(value="-- fps")
        ttk.Label(status, textvariable=self.fps_var).grid(row=1, column=1, sticky="w", **pad)

        self.eta_var = tk.StringVar(value="ETA: --")
        ttk.Label(status, textvariable=self.eta_var).grid(row=2, column=0, columnspan=2, sticky="w", **pad)

        self.util_var = tk.StringVar(value="Utilization: --")
        ttk.Label(status, textvariable=self.util_var).grid(row=3, column=0, columnspan=2, sticky="w", **pad)

        self.power_var = tk.StringVar(value="Power: --")
        ttk.Label(status, textvariable=self.power_var).grid(row=4, column=0, columnspan=2, sticky="w", **pad)

        self.output_status_var = tk.StringVar(value="Output: --")
        ttk.Label(status, textvariable=self.output_status_var).grid(row=5, column=0, columnspan=2, sticky="w", **pad)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(150, self.drain_events)
        self._stats_stop = threading.Event()
        threading.Thread(target=self._stats_loop, daemon=True).start()

    def browse_clips(self):
        paths = filedialog.askopenfilenames(
            title="Select GoPro video files",
            filetypes=[("MP4 videos", "*.mp4 *.MP4"), ("All files", "*.*")],
        )
        if not paths:
            return
        self.clips = sorted((pathlib.Path(p) for p in paths), key=lambda p: p.name)
        self.clips_var.set(f"{len(self.clips)} file(s) selected")
        self.clips_list.delete(0, tk.END)
        for c in self.clips:
            self.clips_list.insert(tk.END, c.name)
        self.update_start_state()

    def on_profile_change(self):
        profile = self.profile_var.get()
        self.current_profile = profile
        is_gpu = is_gpu_profile(profile, self.profile_specs)
        output = self.profile_specs.get(profile, {}).get("output", [])

        preset_choices = [f"p{n}" for n in range(1, 8)] if is_gpu else [str(n) for n in range(0, 14)]
        self.preset_combo.configure(values=preset_choices)

        quality_flag = "-cq" if is_gpu else "-crf"
        self.quality_var.set(int(extract_flag_value(output, quality_flag, "24" if is_gpu else "20")))
        self.preset_var.set(extract_flag_value(output, "-preset", preset_choices[0] if preset_choices else ""))

        suggestions = QUALITY_SUGGESTIONS_GPU if is_gpu else QUALITY_SUGGESTIONS_CPU
        for level, btn in self.quality_preset_buttons.items():
            btn.configure(text=f"{level} ({suggestions[level]})")

        preset_suggestions = PRESET_SUGGESTIONS_GPU if is_gpu else PRESET_SUGGESTIONS_CPU
        for level, btn in self.preset_preset_buttons.items():
            btn.configure(text=f"{level} ({preset_suggestions[level]})")

        is_720p = "720p" in profile
        if is_720p != getattr(self, "_last_profile_is_720p", None):
            target_layout = "default-1280x720.xml" if is_720p else "default-5312x2988.xml"
            if target_layout in self.layouts:
                self.layout_var.set(target_layout)
        self._last_profile_is_720p = is_720p

    def set_quality_preset(self, level):
        is_gpu = is_gpu_profile(self.profile_var.get(), self.profile_specs)
        suggestions = QUALITY_SUGGESTIONS_GPU if is_gpu else QUALITY_SUGGESTIONS_CPU
        self.quality_var.set(suggestions[level])

    def set_speed_preset(self, level):
        is_gpu = is_gpu_profile(self.profile_var.get(), self.profile_specs)
        suggestions = PRESET_SUGGESTIONS_GPU if is_gpu else PRESET_SUGGESTIONS_CPU
        self.preset_var.set(suggestions[level])

    def browse_ride(self):
        path = filedialog.askopenfilename(
            title="Select ride data file",
            filetypes=[("FIT/GPX files", "*.fit *.gpx"), ("All files", "*.*")],
        )
        if not path:
            return
        self.ride_file = pathlib.Path(path)
        self.ride_var.set(str(self.ride_file))
        if not self.output_var.get():
            default_out = self.ride_file.with_name(f"dashboard_{self.ride_file.stem}.mp4")
            self.output_var.set(str(default_out))
        self.update_start_state()

    def browse_output(self):
        initial = self.output_var.get() or "dashboard_output.mp4"
        initial_path = pathlib.Path(initial)
        path = filedialog.asksaveasfilename(
            title="Choose output file",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4")],
            initialfile=initial_path.name,
            initialdir=str(initial_path.parent) if initial_path.parent.exists() else None,
        )
        if not path:
            return
        self.output_var.set(path)
        self.update_start_state()

    def update_start_state(self):
        ok = bool(self.clips) and self.ride_file is not None and self.output_var.get().strip()
        self.start_btn.configure(state="normal" if ok else "disabled")

    def start(self):
        self.output_file = pathlib.Path(self.output_var.get())
        self.output_status_var.set(f"Output: {self.output_file}")
        self.start_btn.configure(state="disabled")
        self.progress.configure(mode="determinate", value=0)
        self.stage_var.set("Starting...")
        profile = self.profile_var.get()
        self.job = RenderJob(
            clips=self.clips,
            ride_file=self.ride_file,
            output_file=self.output_file,
            profile=profile,
            layout=self.layout_var.get(),
            quality=self.quality_var.get(),
            preset=self.preset_var.get(),
            overlay_size="1280x720" if "720p" in profile else None,
            profile_specs=self.profile_specs,
            events=self.events,
        )
        threading.Thread(target=self.job.run, daemon=True).start()

    def drain_events(self):
        try:
            while True:
                kind, *rest = self.events.get_nowait()
                if kind == "stage":
                    self.stage_var.set(rest[0])
                elif kind == "indeterminate":
                    self.progress.configure(mode="indeterminate")
                    self.progress.start(15)
                elif kind == "determinate":
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                elif kind == "progress":
                    pct, rate, eta = rest
                    self.progress.configure(value=pct)
                    self.fps_var.set(f"{rate} fps")
                    self.eta_var.set(f"ETA: {eta}")
                elif kind == "error":
                    self.stage_var.set("Error")
                    self.progress.stop()
                    self.eta_var.set("ETA: --")
                    self.start_btn.configure(state="normal")
                    messagebox.showerror("Render failed", rest[0])
                elif kind == "done":
                    self.start_btn.configure(state="normal")
                    output_path = pathlib.Path(rest[0])
                    messagebox.showinfo("Render Complete", f"Output file:\n{output_path}")
                    self.open_containing_folder(output_path)
                elif kind == "stats":
                    mode, util, power = rest
                    self.util_var.set(f"{mode} Utilization: {util}")
                    self.power_var.set(f"{mode} Power: {power}")
        except queue.Empty:
            pass
        self.root.after(150, self.drain_events)

    def _stats_loop(self):
        # Runs on a background thread so a slow powershell/nvidia-smi invocation never
        # freezes the UI; results are pushed through the same events queue as render progress.
        while not self._stats_stop.is_set():
            if is_gpu_profile(self.current_profile, self.profile_specs):
                mode, util, power = "GPU", *self._query_gpu_stats()
            else:
                mode, util, power = "CPU", *self._query_cpu_stats()
            self.events.put(("stats", mode, util, power))
            self._stats_stop.wait(1.5)

    @staticmethod
    def _query_gpu_stats():
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2, creationflags=NO_WINDOW_FLAGS,
            )
            if out.returncode == 0 and out.stdout.strip():
                util, power = [x.strip() for x in out.stdout.strip().split(",")]
                return f"{util}%", f"{power} W"
        except Exception:
            pass
        return "--", "--"

    @staticmethod
    def _query_cpu_stats():
        # LoadPercentage is standard WMI, works everywhere. Power Meter (\Power Meter(*)\Power)
        # is a best-effort read: only populated on hardware/drivers that expose energy metering,
        # so it commonly reports nothing - fall back to "N/A" rather than erroring.
        script = (
            "$loads = (Get-CimInstance Win32_Processor).LoadPercentage; "
            "$load = ($loads | Measure-Object -Average).Average; "
            "try { $p = (Get-Counter '\\Power Meter(*)\\Power' -ErrorAction Stop)."
            "CounterSamples | Select-Object -First 1 -ExpandProperty CookedValue } "
            "catch { $p = -1 }; "
            "\"$load,$p\""
        )
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True, text=True, timeout=3, creationflags=NO_WINDOW_FLAGS,
            )
            if out.returncode == 0 and out.stdout.strip():
                load_str, power_str = out.stdout.strip().splitlines()[-1].split(",")
                util = f"{float(load_str):.0f}%"
                milliwatts = float(power_str)
                power = f"{milliwatts / 1000:.1f} W" if milliwatts > 0 else "N/A (unsupported)"
                return util, power
        except Exception:
            pass
        return "--", "N/A (unsupported)"

    def open_containing_folder(self, path):
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", f"/select,{path}"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(pathlib.Path(path).parent)])
        except Exception:
            pass

    def on_close(self):
        self._stats_stop.set()
        if self.job is not None:
            self.job.cancel()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
