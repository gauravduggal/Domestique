import subprocess
import sys

# On Windows, a process with no console of its own (e.g. this tool frozen into a windowed
# .exe) makes Windows allocate a brand new, visible console window for any console-subsystem
# child it spawns (ffmpeg, ffprobe) unless told not to. Harmless when a console already
# exists (e.g. running from a normal terminal): it only suppresses allocating a *new* one.
NO_WINDOW_KWARGS = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, **{**NO_WINDOW_KWARGS, **kwargs})


def invoke(cmd, **kwargs):
    try:
        return run(cmd, **kwargs, text=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise IOError(f"Error: {cmd}\n stdout: {e.stdout}\n stderr: {e.stderr}")
