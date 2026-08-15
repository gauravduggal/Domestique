# ==============================
# Build a portable, self-contained distribution of Domestique (the GoPro dashboard render GUI).
#
# Produces dist\Domestique\ containing:
#   - gopro-dashboard-gui.exe, gopro-dashboard.exe, gopro-join-list.exe (+ shared _internal\)
#   - ffmpeg\bin\ffmpeg.exe, ffprobe.exe (copied from C:\ffmpeg\bin - the exact build tested
#     all session, including the d3d11va NVENC fix and libsvtav1 CPU encode)
#   - go_pro_graphics\ffmpeg-profiles.json, gopro_overlay\layouts\*.xml (via the spec's datas)
# and zips it to dist\Domestique-portable.zip.
# ==============================

$ErrorActionPreference = "Stop"
# This venv's python.exe wrapper writes a benign conda-detection warning to stderr on every
# invocation; PowerShell 7.3+'s $PSNativeCommandUseErrorActionPreference would otherwise promote
# that stderr chatter into a terminating error under $ErrorActionPreference = "Stop" above.
$PSNativeCommandUseErrorActionPreference = $false

$RepoDir = "C:\gopro-dashboard-overlay"
$Python = "$RepoDir\.venv\Scripts\python.exe"
$Spec = "$RepoDir\packaging\gopro-dashboard-gui.spec"
$DistDir = "$RepoDir\dist"
$BuildDir = "$RepoDir\build"
$SourceFfmpegDir = "C:\ffmpeg\bin"

Set-Location $RepoDir

& $Python -m PyInstaller --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Output "Installing PyInstaller..."
    & $Python -m pip install pyinstaller
}

Write-Output "Building executables..."
& $Python -m PyInstaller $Spec --distpath $DistDir --workpath $BuildDir --clean --noconfirm

$OutDir = "$DistDir\Domestique"

Write-Output "Bundling ffmpeg..."
$FfmpegOutDir = "$OutDir\ffmpeg\bin"
New-Item -ItemType Directory -Force -Path $FfmpegOutDir | Out-Null
Copy-Item "$SourceFfmpegDir\ffmpeg.exe" -Destination $FfmpegOutDir -Force
Copy-Item "$SourceFfmpegDir\ffprobe.exe" -Destination $FfmpegOutDir -Force

Write-Output "Zipping..."
$ZipPath = "$DistDir\Domestique-portable.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path $OutDir -DestinationPath $ZipPath

Write-Output "Done: $ZipPath"
