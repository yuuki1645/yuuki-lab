# Isaac 学習ログ API の起動例（Windows）
# yuuki-lab/isaac-lab の TensorBoard ログルートを明示してサーバーを起動する。
# 0.0.0.0 で待ち受けるため LAN / Tailscale 経由でも同じポートに到達できます。

$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$LogRoot = Join-Path $RepoRoot "isaac-lab\logs\rsl_rl"
$env:ISAAC_RL_LOG_ROOT = $LogRoot
$env:ISAAC_RL_LOG_HOST = "0.0.0.0"
Set-Location $PSScriptRoot

# 古い API が 8792 を掴んだままだと log_root が古い値のままになるため、先に解放する
$port = 8792
$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $listeners) {
  $procId = $conn.OwningProcess
  if ($procId -and $procId -ne 0) {
    Write-Host "[isaac_rl_log] Stopping existing listener on :$port (PID $procId)" -ForegroundColor Yellow
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
  }
}

try {
  $tsIp = tailscale ip -4 2>$null
  if ($tsIp) {
    Write-Host "[isaac_rl_log] Tailscale API: http://${tsIp}:8792" -ForegroundColor Cyan
  }
} catch {
  # tailscale CLI 未インストール時は無視
}

Write-Host "[isaac_rl_log] log_root: $LogRoot" -ForegroundColor Green
python isaac_rl_log_server.py --log-root $LogRoot
