# Pico W 圧力テレメトリ・ブリッジ（Flask + Socket.IO）起動
# Hub の実機テレメトリ画面が http://<このPC>:8793 を購読する。
# Pico は POST http://192.168.100.104:8793/api/pressure/sample へ送る想定。

Set-Location $PSScriptRoot

$port = 8793
$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $listeners) {
  $procId = $conn.OwningProcess
  if ($procId -and $procId -ne 0) {
    Write-Host "[pressure] Stopping existing listener on :$port (PID $procId)" -ForegroundColor Yellow
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
  }
}

$env:PRESSURE_TELEMETRY_HOST = "0.0.0.0"
$env:PRESSURE_TELEMETRY_PORT = "$port"

Write-Host "[pressure] Pico POST: http://192.168.100.104:${port}/api/pressure/sample" -ForegroundColor Cyan
Write-Host "[pressure] Hub Socket.IO: http://192.168.100.104:${port}" -ForegroundColor Cyan
python pressure_telemetry_server.py
