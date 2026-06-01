# exp_021: ビューアなし・wandb 有効で学習を複数プロセス並列起動する。
#
# 使い方（本フォルダで）:
#   .\launch_parallel.ps1
#   .\launch_parallel.ps1 -Count 4
#
# 実行ポリシーでブロックされた場合:
#   powershell -ExecutionPolicy Bypass -File .\launch_parallel.ps1
#
# ログをファイルに残す:
#   .\launch_parallel.ps1 -RedirectLogs -LogDir logs\parallel

param(
  [int]$Count = 10,
  [string]$LogDir = "",
  [switch]$RedirectLogs
)

$ErrorActionPreference = "Stop"

$ExpDir = $PSScriptRoot
Set-Location $ExpDir

$TrainArgs = @(
  "train.py",
  "--no-viewer",
  "--step-wall-sleep", "0",
  "--no-telemetry"
)

if ($LogDir -ne "") {
  $RedirectLogs = $true
}
if ($RedirectLogs) {
  if ($LogDir -eq "") {
    $LogDir = Join-Path $ExpDir "logs\parallel"
  }
  New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

Write-Host "[launch] exp dir: $ExpDir"
Write-Host "[launch] starting $Count process(es) | wandb=on (default) | viewer=off | telemetry=off"

1..$Count | ForEach-Object {
  $i = $_
  $procArgs = @{
    FilePath         = "python"
    ArgumentList     = $TrainArgs
    WorkingDirectory = $ExpDir
  }
  if ($RedirectLogs) {
    $procArgs["RedirectStandardOutput"] = Join-Path $LogDir "run_$i.out.log"
    $procArgs["RedirectStandardError"] = Join-Path $LogDir "run_$i.err.log"
    $procArgs["NoNewWindow"] = $true
  }
  Start-Process @procArgs
  Write-Host "[launch] started #$i"
}

Write-Host "[launch] done. Check: Get-Process python"
Write-Host "[launch] wandb dashboard for new runs; local ckpt dirs match wandb Run Name."
