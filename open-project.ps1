param(
    [ValidateRange(1024, 65535)][int]$Port = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$projectUrl = "http://127.0.0.1:$Port"
$runtimeRoot = Join-Path $projectRoot 'runtime'

function Get-ProjectStatus {
    try {
        return Invoke-RestMethod -Uri "$projectUrl/api/status" -TimeoutSec 2
    } catch {
        return $null
    }
}

function Test-ProjectReady($status) {
    return ($null -ne $status -and $status.version -and $status.real_llm -eq $true -and $status.backend -like 'Qwen3-*')
}

try {
    Write-Host 'Hostel Cooling - opening your project' -ForegroundColor Green
    $status = Get-ProjectStatus
    if (-not (Test-ProjectReady $status)) {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            throw "Port $Port is already in use by another application or backend mode. Close that service or choose another -Port."
        }
        $projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $projectPython)) {
            $projectPython = (Get-Command python -ErrorAction Stop).Source
        }
        New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
        $stdoutPath = Join-Path $runtimeRoot "launcher-$Port.stdout.log"
        $stderrPath = Join-Path $runtimeRoot "launcher-$Port.stderr.log"
        $server = Start-Process -FilePath $projectPython -ArgumentList @('-m', 'hostel_cooling', 'serve', '--port', "$Port") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
        Set-Content -LiteralPath (Join-Path $runtimeRoot "launcher-$Port.pid") -Value $server.Id -Encoding ASCII
        $deadline = [DateTime]::UtcNow.AddSeconds(120)
        Write-Host 'Starting the application and local model. Please wait...'
        while ([DateTime]::UtcNow -lt $deadline) {
            $status = Get-ProjectStatus
            if (Test-ProjectReady $status) { break }
            $server.Refresh()
            if ($server.HasExited) {
                $details = (Get-Content -LiteralPath $stderrPath -Tail 10 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
                throw "The application could not start. On a new machine, run setup.bat once.$([Environment]::NewLine)$details"
            }
            Start-Sleep -Milliseconds 500
        }
        if (-not (Test-ProjectReady $status)) {
            throw "Startup is taking longer than expected. Check $stderrPath and runtime\llm logs."
        }
    }
    Write-Host "Ready: $projectUrl" -ForegroundColor Green
    Write-Host "Model: $($status.backend)"
    if (-not $NoBrowser) {
        # The browser is the user's interactive application window.
        Start-Process -FilePath $projectUrl
    }
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
