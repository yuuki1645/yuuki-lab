# Pico W 圧力テレメトリ・ブリッジ起動
# - 先に :8793 を掴んでいる全プロセスを落とす（127.0.0.1 と 0.0.0.0 の二重待ち受け防止）
# - 常に 0.0.0.0 で待ち受ける（localhost Hub と LAN Pico が同じプロセスを見る）

Set-Location $PSScriptRoot

$port = 8793

function Stop-PortListeners([int]$Port) {
  $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($procId in $listeners) {
    if (-not $procId -or $procId -eq 0) { continue }
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    $name = if ($proc) { $proc.ProcessName } else { "?" }
    Write-Host "[pressure] Stopping listener on :$Port (PID $procId, $name)" -ForegroundColor Yellow
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Milliseconds 400
  $left = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
  if ($left.Count -gt 0) {
    Write-Host "[pressure] WARNING: port $Port still has $($left.Count) listener(s)" -ForegroundColor Red
  } else {
    Write-Host "[pressure] Port $Port is free" -ForegroundColor Green
  }
}

Stop-PortListeners -Port $port

$env:PRESSURE_TELEMETRY_HOST = "0.0.0.0"
$env:PRESSURE_TELEMETRY_PORT = "$port"

Write-Host "[pressure] Pico POST:    http://192.168.100.104:${port}/api/pressure/sample" -ForegroundColor Cyan
Write-Host "[pressure] Hub Socket.IO: http://192.168.100.104:${port}  (localhost も同じプロセス)" -ForegroundColor Cyan
python pressure_telemetry_server.py --host 0.0.0.0 --port $port
