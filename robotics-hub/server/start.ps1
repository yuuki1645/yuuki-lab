# Isaac 学習ログ API の起動例（Windows）
# test-isaac-project の TensorBoard ログルートを明示してサーバーを起動する。
# 0.0.0.0 で待ち受けるため LAN / Tailscale 経由でも同じポートに到達できます。

$env:ISAAC_RL_LOG_ROOT = "C:\Users\yuukilab\test-isaac-project\TestIsaacProject\logs\rsl_rl"
$env:ISAAC_RL_LOG_HOST = "0.0.0.0"
Set-Location $PSScriptRoot

# 起動前に Tailscale URL を表示（参考）
try {
  $tsIp = tailscale ip -4 2>$null
  if ($tsIp) {
    Write-Host "[isaac_rl_log] Tailscale API: http://${tsIp}:8792" -ForegroundColor Cyan
  }
} catch {
  # tailscale CLI 未インストール時は無視
}

python isaac_rl_log_server.py
