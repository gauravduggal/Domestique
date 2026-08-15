#!/usr/bin/env python3

import argparse
import pathlib

from gopro_overlay.assertion import assert_file_exists
from gopro_overlay.ffmpeg import FFMPEG
from gopro_overlay.ffmpeg_gopro import FFMPEGGoPro
from gopro_overlay.log import log

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Concatenate an explicit list of GoPro files")
    parser.add_argument("--ffmpeg-dir", type=pathlib.Path,
                        help="Directory where ffmpeg/ffprobe located, default=Look in PATH")
    parser.add_argument("output", type=pathlib.Path, help="Output MP4 file")
    parser.add_argument("inputs", type=pathlib.Path, nargs="+",
                        help="MP4 files to join, in order")

    args = parser.parse_args()

    sources = [assert_file_exists(p) for p in args.inputs]

    log(f"Joining: {[p.name for p in sources]}")

    ffmpeg_gopro = FFMPEGGoPro(FFMPEG(args.ffmpeg_dir))
    ffmpeg_gopro.join_files(filepaths=sources, output=args.output)
