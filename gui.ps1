# ==============================
# Launch Domestique (the GoPro dashboard render GUI)
# ==============================

$RepoDir = "C:\gopro-dashboard-overlay"

Set-Location $RepoDir

& ".\.venv\Scripts\python.exe" ".\.venv\Scripts\gopro-dashboard-gui.py"
