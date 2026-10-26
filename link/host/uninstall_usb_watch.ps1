#requires -Version 5.1
<#
.SYNOPSIS
  サインイン時の監視登録を外し、動いている usb_hub_watch.ps1 を止める。

.NOTES
  robotics-hub と lab_debug.py は止めない。実験中の COM と画面を残すため。
#>

$ErrorActionPreference = "Continue"

$startup = [Environment]::GetFolderPath("Startup")
$lnkPath = Join-Path $startup "yuuki-lab USB Hub.lnk"
if (Test-Path -LiteralPath $lnkPath) {
    Remove-Item -LiteralPath $lnkPath -Force
    Write-Output "スタートアップから外した"
    Write-Output $lnkPath
} else {
    Write-Output "スタートアップには無かった"
}

$watchers = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -eq "powershell.exe" -and $_.CommandLine -and $_.CommandLine -like "*usb_hub_watch.ps1*"
})
foreach ($proc in $watchers) {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Output ("監視を止めた PID " + $proc.ProcessId)
}
if ($watchers.Count -eq 0) {
    Write-Output "動いている監視は無かった"
}
