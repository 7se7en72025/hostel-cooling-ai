param([string]$Destination)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$studyRoot = Join-Path $projectRoot 'outputs\study'
if (-not $Destination) {
    $Destination = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Hostel Cooling - Final Project'
}
# Keep any existing folder, including presentation edits made by the user.
if (Test-Path -LiteralPath $Destination) {
    $Destination += ' - ' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
}
New-Item -ItemType Directory -Path $Destination -ErrorAction Stop | Out-Null
$artifacts = [ordered]@{
    '01_Final_Report.pdf' = 'Hostel_Cooling_Project_Report.pdf'
    '02_Editable_Presentation.pptx' = 'Hostel_Cooling_Final_Presentation.pptx'
    '03_Presentation.pdf' = 'Hostel_Cooling_Final_Presentation.pdf'
    '04_Viva_Guide.pdf' = 'Hostel_Cooling_Viva_Guide.pdf'
}
foreach ($entry in $artifacts.GetEnumerator()) {
    $source = Join-Path $studyRoot $entry.Value
    Copy-Item -LiteralPath $source -Destination (Join-Path $Destination $entry.Key)
    if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath (Join-Path $Destination $entry.Key)).Hash) {
        throw "Copy verification failed: $($entry.Key)"
    }
}
$archive = Join-Path (Split-Path -Parent $projectRoot) 'Hostel_Cooling_Final_Submission.zip'
if (-not (Test-Path -LiteralPath $archive)) { throw 'Build the submission ZIP first: python tools/build_submission.py' }
Copy-Item -LiteralPath $archive -Destination (Join-Path $Destination '05_Complete_Project.zip')
$launcherPath = Join-Path $projectRoot 'open-project.bat'
$launcher = "@echo off`r`ncall `"$launcherPath`" %*`r`n"
Set-Content -LiteralPath (Join-Path $Destination 'OPEN_PROJECT.bat') -Value $launcher -Encoding ASCII
Set-Content -LiteralPath (Join-Path $Destination 'Dashboard.url') -Value "[InternetShortcut]`r`nURL=http://127.0.0.1:8765/`r`n" -Encoding ASCII
$guide = @'
HOSTEL COOLING - FINAL PROJECT

APP CHALANE KE LIYE:
Double-click OPEN_PROJECT.bat.
It starts the application and local model, then opens the dashboard in your browser.
If already running, it opens the existing application.

FINAL FILES:
01_Final_Report.pdf             Final 14-page report
02_Editable_Presentation.pptx   Editable PowerPoint with speaker notes
03_Presentation.pdf            Slides you can open without PowerPoint
04_Viva_Guide.pdf              34 questions, answers and key numbers
05_Complete_Project.zip        All final files, source code and raw research evidence

PowerPoint installed nahi hai? Open 03_Presentation.pdf to view the slides.
To edit the PPTX, use PowerPoint or another compatible presentation editor.

OPEN_PROJECT.bat uses the prepared project on this computer. Keep the original
Desktop/projects/hostel-cooling-ai folder in place.
For a different computer: extract 05_Complete_Project.zip, open 05_Source_Code,
install Python 3.11+, run setup.bat once, then double-click open-project.bat.
Initial setup downloads the pinned local model (about 2.5 GB).

The approved study uses simulated room/occupant data. Model inference and the
software computations actually ran. All evidence is included in the ZIP.
'@
Set-Content -LiteralPath (Join-Path $Destination 'START_HERE.txt') -Value $guide -Encoding ASCII
Write-Output "Desktop folder ready: $Destination"
