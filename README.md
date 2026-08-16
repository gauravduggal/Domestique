# Domestique

### A cycling-focused GoPro dashboard overlay tool

Render speed, power, cadence, heart rate, and gradient straight onto your ride footage.

<a href="https://github.com/time4tea/gopro-dashboard-overlay/discussions"><img alt="GitHub Discussions" src="https://img.shields.io/github/discussions/time4tea/gopro-dashboard-overlay?style=for-the-badge"></a>
<a href="https://pypi.org/project/gopro-overlay/"><img alt="PyPI" src="https://img.shields.io/pypi/v/gopro-overlay?style=for-the-badge"></a>
<a href="https://hub.docker.com/r/overlaydash/gopro-dashboard-overlay"><img alt="Docker" src="https://img.shields.io/docker/v/overlaydash/gopro-dashboard-overlay?label=Docker&style=for-the-badge"></a>

- Cycling-tuned dashboard layouts - speed, power, cadence, heart rate, gradient
- Standalone GUI, packaged as a self-contained app - no Python install needed to run it
- AV1 encoding profiles (GPU/NVENC and CPU/SVT-AV1) for 5K, 4K, and 720p output
- Also works as a general GoPro/GPX/FIT overlay tool - multiple resolutions, most GoPro models, Linux/Mac/Windows

Domestique is a fork of [gopro-dashboard-overlay](https://github.com/time4tea/gopro-dashboard-overlay) - full
credit to the original project for the underlying rendering engine. The badges above and much of the reference
documentation below (map styles, XML layout format, `pip`/Docker install) still point at the upstream project.

## Quick Start

The easiest way to use Domestique is the packaged GUI - build it once, then just run the app, no Python needed
after that. Full details (prerequisites, troubleshooting) are in [packaging/README.md](packaging/README.md).

### 1. Generate the package

**Windows** (PowerShell):
```powershell
.\packaging\build.ps1
```

**macOS/Linux:**
```bash
./packaging/build.sh
```

Both produce `dist/Domestique-portable.zip` - a self-contained build with the GUI, `ffmpeg`, layouts, and encoding
profiles all bundled in.

### 2. Install it

The app is portable - extract it to wherever you want to keep it and run it from there. It doesn't need
installing beyond that.

**Windows** (PowerShell):
```powershell
Expand-Archive -Path dist\Domestique-portable.zip -DestinationPath "$env:LOCALAPPDATA\Domestique" -Force
```
This creates a `Domestique\` folder at the destination containing the app.

**macOS/Linux:**
```bash
./packaging/install.sh
# or install somewhere other than the ~/Applications default:
./packaging/install.sh /opt/domestique
```
This unzips to a `Domestique/` folder at the destination and makes the bundled executables runnable.

### 3. Run it

**Windows:**
```powershell
& "$env:LOCALAPPDATA\Domestique\Domestique\gopro-dashboard-gui.exe"
```
(or just double-click `gopro-dashboard-gui.exe` in that folder)

**macOS/Linux:** `install.sh` prints the exact path to run, e.g.:
```bash
~/Applications/Domestique/gopro-dashboard-gui
```
First launch on macOS may need a right-click → Open instead, to get past Gatekeeper since the app isn't
code-signed.

Pick your GoPro clip(s), a FIT/GPX ride file, an encoding profile (`av1_nvenc_*` for an NVIDIA GPU,
`av1_cpudec_cpuenc*` for CPU-only), a quality/speed preset, and hit **Start Render**.

## Map Styles

Almost 30 different map styles are supported! - See [map styles](docs/maps/README.md) for more

*Example*

| .                                   | .                                             | .                                                     | .                                                     |
|-------------------------------------|-----------------------------------------------|-------------------------------------------------------|-------------------------------------------------------|
| ![osm](docs/maps/map_style_osm.png) | ![tf-cycle](docs/maps/map_style_tf-cycle.png) | ![tf-transport](docs/maps/map_style_tf-transport.png) | ![tf-landscape](docs/maps/map_style_tf-landscape.png) |


## Requirements

- Python3.10 (development is done on Python3.11)
- ffmpeg (you'll need the ffmpeg program installed)
- libraqm (needed by [Pillow](https://pypi.org/project/Pillow/))

## Installation

For Windows, please see docs [docs/windows.md](docs/windows.md)

For Docker, please see docs at [docs/docker.md](docs/docker.md)

Install locally using `pip`, or use the provided Docker image

Optional: Some widgets require the `cairo` library - which must be installed separately.


### Installing and running from source

Domestique isn't published to PyPI - the [Quick Start](#quick-start) above (packaged GUI) is the easiest way to
run it without setting up Python at all. To install from source instead:

```shell
python -m venv venv
venv/bin/pip install -e .
```

The Roboto font needs to be installed on your system. You could install it with one of the following commands maybe.

```bash
pacman -S ttf-roboto
apt install truetype-roboto
apt install fonts-roboto
```

#### (Optional) Installing pycairo

Optionally, install `pycairo`

```shell
venv/bin/pip install pycairo==1.23.0
```

You might need to install some system libraries - This is what the pycairo docs suggest: 

Ubuntu/Debian: `sudo apt install libcairo2-dev pkg-config python3-dev`

macOS/Homebrew: `brew install cairo pkg-config`

### Example

For full instructions on all command lines see [docs/bin](docs/bin)

```shell
venv/bin/gopro-dashboard.py --gpx ~/Downloads/Morning_Ride.gpx --privacy 52.000,-0.40000,0.50 ~/gopro/GH020073.MP4 GH020073-dashboard.MP4
```

## Caveats

The GPS track in Hero 9 seems to be very poor. If you supply a GPX file from a Garmin or whatever, the
program will use this instead for the GPS. Hero 11 GPS is much improved.

Privacy allows you to set a privacy zone. Various widgets will not draw points within that zone.

The data recorded in the GoPro video will uses GPS time, which (broadly) is UTC. The renderer will use your local
timezone to interpret this, and use the local timezone. This may produce strange results if you go on holiday somewhere,
but then render the files when you get back home! On linux you can use the TZ variable to change the timezone that's
used.

## Writeups

There's a great writeup of how to use the software to make an overlay from a GPX file at https://blog.cubieserver.de/2022/creating-gpx-overlay-videos-on-linux/
(Nov 2022)

### Format of the Dashboard Configuration file

Several dashboards are built-in to the software, but the dashboard layout is highly configurable, controlled by an XML
file.

For more information on the (extensive) configurability of the layout please see [docs/xml](docs/xml) and lots
of [examples](docs/xml/examples/README.md)

## FFMPEG Control & GPUs

FFMPEG has **a lot** of options! This program comes with some mostly sensible defaults, but to use GPUs and control the
output much more carefully, including framerates and bitrates, you can use a JSON file containing a number of 'profiles'
and select the profile you want when running the program.

For more details on how to select these, and an example of Nvidia GPU, please see the guide in [docs/bin#ffmpeg-profiles](docs/bin#ffmpeg-profiles)

Please also see other docs [PERFORMANCE.md](PERFORMANCE.md) and [docs/bin/PERFORMANCE_GUIDE.md](docs/bin/PERFORMANCE_GUIDE.md)

## Converting to GPX files

```shell
venv/bin/gopro-to-gpx.py <input-file> [output-file]
```

## Joining a sequence of MP4 files together

Use the gopro-join.py command. Given a single file from the sequence, it will find and join together all the files. If
you have any problems with this, please do raise an issue - I don't have that much test data.

The joined file almost certainly won't work in the GoPro tools! - But it should work with `gopro-dashboard.py` - I will
look into the additional technical stuff required to make it work in the GoPro tools.

*This will require a lot of disk space!*

```shell
venv/bin/gopro-join.py /media/sdcard/DCIM/100GOPRO/GH030170.MP4 /data/gopro/nice-ride.MP4
```

## Cutting a section from a GoPro file

You can cut a section of the gopro file, with metadata.


## Related Software

- https://github.com/Romancha/GPStitch - A VERY nice web user interface for this program.

- https://github.com/julesgraus/interactiveGoProDashboardTool - An interactive helper to build the command line for the dashboard program

## Icons

Icon files in [icons](gopro_overlay/icons) are not covered by the MIT licence

## Map Data

Data © [OpenStreetMap contributors](http://www.openstreetmap.org/copyright)

Some Maps © [Thunderforest](http://www.thunderforest.com/)

## References

https://github.com/juanmcasillas/gopro2gpx

https://github.com/JuanIrache/gopro-telemetry

https://github.com/gopro/gpmf-parser

https://coderunner.io/how-to-compress-gopro-movies-and-keep-metadata/

## Other Related Software


- https://github.com/progweb/gpx2video

- https://github.com/JuanIrache/gopro-telemetry

## Upstream Engine Changelog

Domestique's own changes are new and not yet broken out into a separate changelog. The history below is
inherited from the upstream rendering engine this fork is built on - see [CHANGELOG.md](CHANGELOG.md) for the
full list, or the [upstream project](https://github.com/time4tea/gopro-dashboard-overlay) for anything newer
than what was forked here.

