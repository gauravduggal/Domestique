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

$RepoDir = "C:\gopro-dashboard-overlay"
$Python = "$RepoDir\.venv\Scripts\python.exe"
$Spec = "$RepoDir\packaging\gopro-dashboard-gui.spec"
$DistDir = "$RepoDir\dist"
$BuildDir = "$RepoDir\build"
$SourceFfmpegDir = "C:\ffmpeg\bin"

Set-Location $RepoDir

# This venv's python.exe wrapper writes a benign conda-detection warning to stderr on every
# invocation. Under $ErrorActionPreference = "Stop", PowerShell promotes ANY native-command
# stderr output into a terminating error - via $PSNativeCommandUseErrorActionPreference on
# PowerShell 7.3+, and via a separate, older mechanism on Windows PowerShell 5.1 too (tested:
# 2>$null redirection alone does not prevent either, and setting
# $PSNativeCommandUseErrorActionPreference = $false is a no-op on 5.1 since that variable didn't
# exist yet). Locally relaxing $ErrorActionPreference to "Continue" around each native call, then
# checking $LASTEXITCODE by hand, is the one approach that works on both.
function Invoke-Native {
    param(
        [Parameter(Mandatory)][string]$Exe,
        [switch]$AllowFailure,
        [Parameter(ValueFromRemainingArguments)][string[]]$ExeArgs
    )
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Exe @ExeArgs
    } finally {
        $ErrorActionPreference = $prevEAP
    }
    if (-not $AllowFailure -and $LASTEXITCODE -ne 0) {
        throw "Command failed (exit ${LASTEXITCODE}): $Exe $($ExeArgs -join ' ')"
    }
}

Invoke-Native $Python -AllowFailure -m PyInstaller --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Output "Installing PyInstaller..."
    Invoke-Native $Python -m pip install pyinstaller
}

Write-Output "Building executables..."
Invoke-Native $Python -m PyInstaller $Spec --distpath $DistDir --workpath $BuildDir --clean --noconfirm

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
