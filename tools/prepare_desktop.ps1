param([string]$Destination)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$studyRoot = Join-Path $projectRoot 'outputs\study'
if (-not $Destination) {
    $Destination = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'Hostel Cooling AI - Professor Handoff'
}
if (Test-Path -LiteralPath $Destination) {
    $Destination += ' - ' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
}
$submitDir = Join-Path $Destination '01 Submit to Professor'
$vivaDir = Join-Path $Destination '02 Take to Viva'
$archive = Join-Path (Split-Path -Parent $projectRoot) 'Hostel_Cooling_Final_Submission.zip'
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
    throw 'Build the submission ZIP first: python tools/build_submission.py'
}
$artifacts = [ordered]@{
    '01 Submit to Professor\01 Final Project Report.pdf' = (Join-Path $studyRoot 'Hostel_Cooling_Project_Report.pdf')
    '01 Submit to Professor\02 Two-Page Project Overview.pdf' = (Join-Path $projectRoot 'hostel_cooling\resources\Hostel_Cooling_Overview.pdf')
    '01 Submit to Professor\03 Presentation Slides.pdf' = (Join-Path $studyRoot 'Hostel_Cooling_Final_Presentation.pdf')
    '01 Submit to Professor\04 Complete Project and Evidence.zip' = $archive
    '02 Take to Viva\01 Editable Presentation.pptx' = (Join-Path $studyRoot 'Hostel_Cooling_Final_Presentation.pptx')
    '02 Take to Viva\02 Viva Questions and Answers.pdf' = (Join-Path $studyRoot 'Hostel_Cooling_Viva_Guide.pdf')
}
foreach ($source in $artifacts.Values) {
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Submission file missing: $source"
    }
}
New-Item -ItemType Directory -Path $submitDir, $vivaDir | Out-Null
foreach ($entry in $artifacts.GetEnumerator()) {
    $target = Join-Path $Destination $entry.Key
    Copy-Item -LiteralPath $entry.Value -Destination $target
    if ((Get-FileHash -LiteralPath $entry.Value).Hash -ne (Get-FileHash -LiteralPath $target).Hash) {
        throw "Copy verification failed: $($entry.Key)"
    }
}

$launcherPath = Join-Path $projectRoot 'open-project.bat'
@(
    '@echo off'
    ('call "{0}" %*' -f $launcherPath)
    'exit /b %errorlevel%'
) | Set-Content -LiteralPath (Join-Path $vivaDir '03 OPEN DASHBOARD.bat') -Encoding ASCII

$guide = @"
HOSTEL COOLING AI
CE F417 + CE F423

SUBMIT TO PROFESSOR

01 Final Project Report.pdf
   The main submission. Start here if the professor asks for one report.
02 Two-Page Project Overview.pdf
   A quick read with the dashboard walkthrough and key study results.
03 Presentation Slides.pdf
   Include if slides are requested. The editable PPTX is in the viva folder.
04 Complete Project and Evidence.zip
   Include if source code, reproducibility files or a complete bundle is requested.

Use the professor's requested file list and upload format when available.

60-SECOND VIVA DEMO

1. Open the editable slides and double-click 03 OPEN DASHBOARD.bat.
2. In My room, select Try the rain example. Point out that both cards use the
   same room and that the rain rule changes the window from open to closed.
3. Close the example and click Get a suggestion. Show the one-hour forecast
   and compare temperature and fan electricity with the fixed schedule.
4. In Study results, explain the trade-off in the seven-day simulation:
   35.1% less fan electricity and 2.4 percentage points more occupied time
   outside the modeled comfort range, compared with a fixed schedule.

Use the Viva Questions and Answers PDF to prepare. The slides PDF works
without PowerPoint.

ON ANOTHER COMPUTER

Extract the ZIP and open 05_Source_Code. On Windows with Python 3.11+,
run setup.bat -DemoOnly, then open-project.bat -Backend offline for the
room demo and study results. Run setup.bat for the full local Qwen model.
"@
Set-Content -LiteralPath (Join-Path $Destination 'START HERE.txt') -Value $guide -Encoding ASCII
Write-Output "Desktop folder ready: $Destination"
