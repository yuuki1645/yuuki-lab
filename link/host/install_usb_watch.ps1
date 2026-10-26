#requires -Version 5.1
<#
.SYNOPSIS
  usb_hub_watch.ps1 を、このユーザーのサインイン時スタートアップへ登録する。

.NOTES
  管理者権限は要らない。ショートカットはスタートアップ フォルダに置く。
  登録したあと、まだ動いていなければ監視を 1 本起動する。再ログオンは要らない。
#>

$ErrorActionPreference = "Stop"

$Watch = Join-Path $PSScriptRoot "usb_hub_watch.ps1"
if (-not (Test-Path -LiteralPath $Watch)) {
    Write-Output "見つからない: $Watch"
    exit 1
}

$startup = [Environment]::GetFolderPath("Startup")
$lnkPath = Join-Path $startup "yuuki-lab USB Hub.lnk"
$powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$repo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = $powershell
# -Sta はトレイアイコンに必要。Hidden なので失敗はログだけに残る。
$lnk.Arguments = "-NoProfile -Sta -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Watch`""
$lnk.WorkingDirectory = $repo
$lnk.WindowStyle = 7
$lnk.Description = "ATOM / CoreS3 を挿すと robotics-hub の実機テレメトリを開く"
$lnk.Save()

Write-Output "スタートアップに登録した"
Write-Output $lnkPath

function Get-WatcherProcesses {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -like "*usb_hub_watch.ps1*"
    })
}

$existing = @(Get-WatcherProcesses)
if ($existing.Count -eq 0) {
    Start-Process -FilePath $powershell -ArgumentList "-NoProfile -Sta -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Watch`"" -WorkingDirectory $repo
    Write-Output "監視を開始した"
} else {
    Write-Output "監視はすでに動いている"
}

Write-Output "外すときは just usb-watch-off または link\host\uninstall_usb_watch.cmd"
