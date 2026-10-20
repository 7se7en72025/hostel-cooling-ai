$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m hostel_cooling serve
