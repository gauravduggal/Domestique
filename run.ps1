# ==============================
# Domestique render script
# Joins a sequence of GoPro clips, then overlays FIT telemetry + custom layout
# ==============================

param(
    [Parameter(Mandatory=$true)]
    [string[]]$Clips,          # GoPro clip filenames (or full paths), in join order

    [Parameter(Mandatory=$true)]
    [string]$Fit,               # FIT filename (or full path) with ride telemetry

    [string]$ClipsDir  = "C:\gopro_overlay_test",
    [string]$OutDir    = "C:\gopro_overlay_test",
    [string]$RepoDir   = "C:\gopro-dashboard-overlay",
    [string]$ConfigDir = "C:\gopro-dashboard-overlay\go_pro_graphics",
    [string]$FontPath  = "C:\Windows\Fonts\arial.ttf",
    [string]$LayoutXml = "C:\gopro-dashboard-overlay\gopro_overlay\layouts\default-5312x2988.xml",
    [string]$FfmpegDir = "C:\ffmpeg\bin",
    [string]$Profile   = "av1_nvenc_5k"
)

# Resolve bare filenames against their default directories; leave absolute paths untouched.
function Resolve-Against($path, $dir) {
    if ([System.IO.Path]::IsPathRooted($path)) { $path } else { Join-Path $dir $path }
}

$ClipPaths  = $Clips | ForEach-Object { Resolve-Against $_ $ClipsDir }
$FitPath    = Resolve-Against $Fit $ClipsDir
$JoinedPath = Join-Path $OutDir "joined_$([System.IO.Path]::GetFileNameWithoutExtension($Fit)).mp4"
$OutputPath = Join-Path $OutDir "dashboard_$([System.IO.Path]::GetFileNameWithoutExtension($Fit)).mp4"

Set-Location $RepoDir

& ".\.venv\Scripts\python.exe" ".\.venv\Scripts\gopro-join-list.py" `
  --ffmpeg-dir $FfmpegDir `
  $JoinedPath `
  @ClipPaths

& ".\.venv\Scripts\python.exe" ".\.venv\Scripts\gopro-dashboard.py" `
  --ffmpeg-dir $FfmpegDir `
  --config-dir $ConfigDir `
  --font $FontPath `
  --layout-xml $LayoutXml `
  --profile $Profile `
  --fit $FitPath `
  --gpx-merge OVERWRITE `
  $JoinedPath `
  $OutputPath
