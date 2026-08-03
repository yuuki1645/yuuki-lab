# npm run dev:pressure 用: :8793 を解放してから圧力ブリッジを起動する
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

$port = 8793
$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $listeners) {
  if ($procId -and $procId -ne 0) {
    Write-Host "[pressure] Freeing :$port (PID $procId)" -ForegroundColor Yellow
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
  }
}
Start-Sleep -Milliseconds 400

$env:PRESSURE_TELEMETRY_HOST = "0.0.0.0"
$env:PRESSURE_TELEMETRY_PORT = "$port"
python "$PSScriptRoot\pressure_telemetry_server.py" --host 0.0.0.0 --port $port
