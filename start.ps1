$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $projectPython) { & $projectPython -m hostel_cooling serve }
else { python -m hostel_cooling serve }
