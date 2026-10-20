param([ValidateSet('cpu','vulkan')][string]$Acceleration='vulkan')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
$projectPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $projectPython -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $projectPython -m hostel_cooling setup-model --acceleration $Acceleration
if ($LASTEXITCODE -ne 0) { throw 'Local model setup failed.' }
& $projectPython -m hostel_cooling train
if ($LASTEXITCODE -ne 0) { throw 'Model training failed.' }
Write-Host 'Setup complete. Run start.bat to open the application, or run-study.bat to reproduce the complete study.'
