# exp_022: ビューアなし・wandb 有効で学習を複数プロセス並列起動する。
#
# 使い方（mujoco-sim から）:
#   .\scripts\launch_exp_022_parallel.ps1
#   .\scripts\launch_exp_022_parallel.ps1 -Count 4
#
# 実行ポリシーでブロックされた場合:
#   powershell -ExecutionPolicy Bypass -File .\scripts\launch_exp_022_parallel.ps1
#
# ログをファイルに残す:
#   .\scripts\launch_exp_022_parallel.ps1 -LogDir logs\exp022

param(
  [int]$Count = 10,
  [string]$LogDir = "",
  [switch]$RedirectLogs
)

$ErrorActionPreference = "Stop"

$MujocoSimRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $MujocoSimRoot

$TrainArgs = @(
  "-m", "mujoco_rl_sim.experiments.exp_022_biped_ppo_hop_balance.train",
  "--no-viewer",
  "--step-wall-sleep", "0",
  "--no-telemetry"
)

if ($LogDir -ne "") {
  $RedirectLogs = $true
}
if ($RedirectLogs) {
  if ($LogDir -eq "") {
    $LogDir = Join-Path $MujocoSimRoot "logs\exp022_parallel"
  }
  New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

Write-Host "[launch] mujoco-sim root: $MujocoSimRoot"
Write-Host "[launch] starting $Count process(es) | wandb=on (default) | viewer=off | telemetry=off"

1..$Count | ForEach-Object {
  $i = $_
  $procArgs = @{
    FilePath     = "python"
    ArgumentList = $TrainArgs
    WorkingDirectory = $MujocoSimRoot
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
