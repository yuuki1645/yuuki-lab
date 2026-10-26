#requires -Version 5.1
<#
.SYNOPSIS
  ATOM S3R / CoreS3（VID 303A）が見えたら robotics-hub を起動し、実機テレメトリを開く。

.NOTES
  このプロセス自身は COM を握り続けない。確認は usb_rt_probe.py が短時間読むだけ。
  Hub と lab_debug.py は、rt-usb のフレームが見えたときだけ npm run dev:m5 で起動する。
  ケーブルを抜いても Hub は止めない。実験の途中でプロセスを落とさないため。
  ログは %LOCALAPPDATA%\yuuki-lab\usb_hub_watch.log。
#>

$ErrorActionPreference = "Continue"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$HubDir = Join-Path $RepoRoot "robotics-hub"
$Probe = Join-Path $PSScriptRoot "usb_rt_probe.py"
$HubUrl = "http://127.0.0.1:5173/m5-telemetry"
$LogPath = Join-Path $env:LOCALAPPDATA "yuuki-lab\usb_hub_watch.log"

# 挿してからポートが安定するまで待つ。列挙直後に開くと、書き込みのリセットとぶつかる。
$StableSeconds = 3
# 無音（ダウンロードモードなど）のあと、同じ挿しっぱなしでアプリ起動へ移った場合の再確認。
$SilentRetrySeconds = 30
# vite が応答するまでの上限。
$HubWaitSeconds = 90
# 文字列のまま渡す。ja-JP だと数値が 1,5 になり、プローブが秒数を読めない。
$ProbeSeconds = "1.5"

$script:seenAt = @{}
$script:silentAt = @{}
$script:pageOpened = $false
$script:absentSince = $null
$script:starting = $false
$script:startAt = Get-Date
$script:lastRepeat = ""

function Write-Log {
    param([string]$Message)
    $dir = Split-Path -Parent $LogPath
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
    if ((Test-Path -LiteralPath $LogPath) -and ((Get-Item -LiteralPath $LogPath).Length -gt 512KB)) {
        Move-Item -LiteralPath $LogPath -Destination ($LogPath + ".bak") -Force
    }
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::AppendAllText($LogPath, $line + "`r`n", $utf8)
}

function Write-LogOnce {
    param([string]$Message)
    if ($script:lastRepeat -eq $Message) {
        return
    }
    $script:lastRepeat = $Message
    Write-Log $Message
}

function Get-AtomComPorts {
    # アプリとダウンロードモードは同じ VID。ここだけでは区別しない。
    $found = New-Object System.Collections.Generic.List[string]
    $items = @(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue)
    foreach ($item in $items) {
        $id = [string]$item.PNPDeviceID
        $name = [string]$item.Name
        if ($id -notmatch "VID_303A") {
            continue
        }
        if ($name -match "\((COM\d+)\)") {
            $port = $Matches[1].ToUpper()
            if (-not $found.Contains($port)) {
                $found.Add($port)
            }
        }
    }
    return ,$found.ToArray()
}

function Test-TcpOpen {
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $wait = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $wait.AsyncWaitHandle.WaitOne(300, $false)
        if (-not $ok) {
            return $false
        }
        $client.EndConnect($wait)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Test-HubPage {
    # TCP が開いただけでは vite の準備前がある。ページが返ってからブラウザを開く。
    if (-not (Test-TcpOpen -Port 5173)) {
        return $false
    }
    try {
        $resp = Invoke-WebRequest -Uri $HubUrl -UseBasicParsing -TimeoutSec 3
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400)
    } catch {
        return $false
    }
}

function Test-FlashBusy {
    # platformio.ini を開いているエディタを誤検出しないよう、語の直後を見る。
    $procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    foreach ($proc in $procs) {
        $name = [string]$proc.Name
        if ($name -match "^(pio|platformio|esptool)(\.exe)?$") {
            return $true
        }
        $cmd = [string]$proc.CommandLine
        if ($cmd -match "(esptool|platformio)(\.exe|\.py)?(\s|$)") {
            return $true
        }
    }
    return $false
}

function Invoke-RtProbe {
    param([string]$Port)
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        Write-Log "python が PATH に無い"
        return 2
    }
    # stdout を関数の戻り値に混ぜない。開けなかった理由はログへ残す。
    $errFile = Join-Path $env:TEMP "yuuki-lab-usb-probe-err.txt"
    & $python.Source $Probe $Port $ProbeSeconds 2> $errFile | Out-Null
    if (Test-Path -LiteralPath $errFile) {
        $errText = [System.IO.File]::ReadAllText($errFile).Trim()
        if ($errText) {
            Write-Log $errText
        }
        Remove-Item -LiteralPath $errFile -Force -ErrorAction SilentlyContinue
    }
    if ($null -eq $LASTEXITCODE) {
        return 2
    }
    return [int]$LASTEXITCODE
}

function Start-DevM5 {
    param([string]$Port)
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) {
        Write-Log "npm.cmd が PATH に無い。Hub は起動しない"
        return $false
    }
    Write-Log "$Port で rt-usb を確認した。npm run dev:m5 を起動する"
    # npm.cmd はバッチなので cmd 経由にする。配列で渡すと引数が割れる。
    $cmd = Join-Path $env:SystemRoot "System32\cmd.exe"
    Start-Process -FilePath $cmd -ArgumentList "/c npm run dev:m5" -WorkingDirectory $HubDir -WindowStyle Minimized
    return $true
}

function Open-HubPage {
    Write-Log "ブラウザを開く $HubUrl"
    Start-Process $HubUrl
}

function Remove-MissingPorts {
    param([string[]]$Ports)
    foreach ($key in @($script:seenAt.Keys)) {
        if ($Ports -notcontains $key) {
            $null = $script:seenAt.Remove($key)
            $null = $script:silentAt.Remove($key)
        }
    }
}

function Invoke-WatchStep {
    # Get-AtomComPorts は配列を 1 個の値として返す。@() で包むと COM が 1 つのとき文字列に崩れる。
    $ports = Get-AtomComPorts
    if ($null -eq $ports) {
        $ports = @()
    }
    if ($ports.Count -eq 0) {
        # リセットや書き込みで COM が一瞬消える。すぐ忘れるとページを連打し、確認もやり直す。
        if ($null -eq $script:absentSince) {
            $script:absentSince = Get-Date
        }
        $goneFor = ((Get-Date) - $script:absentSince).TotalSeconds
        if ($goneFor -ge $StableSeconds) {
            $script:pageOpened = $false
            $script:seenAt = @{}
            $script:silentAt = @{}
            $script:lastRepeat = ""
        }
        return
    }
    $script:absentSince = $null
    Remove-MissingPorts -Ports $ports

    if (Test-HubPage) {
        $script:starting = $false
        if (-not $script:pageOpened) {
            Open-HubPage
            $script:pageOpened = $true
        }
        return
    }

    if ($script:starting) {
        $elapsed = ((Get-Date) - $script:startAt).TotalSeconds
        if ($elapsed -gt $HubWaitSeconds) {
            Write-Log "Hub が $HubWaitSeconds 秒以内に応答しなかった"
            $script:starting = $false
        }
        return
    }

    if (Test-FlashBusy) {
        Write-LogOnce "書き込みプロセスがあるので Hub は起動しない"
        return
    }

    foreach ($port in $ports) {
        if (-not $script:seenAt.ContainsKey($port)) {
            $script:seenAt[$port] = Get-Date
            Write-Log "VID 303A を検出: $port"
        }
        $seenFor = ((Get-Date) - $script:seenAt[$port]).TotalSeconds
        if ($seenFor -lt $StableSeconds) {
            continue
        }
        if ($script:silentAt.ContainsKey($port)) {
            $since = ((Get-Date) - $script:silentAt[$port]).TotalSeconds
            if ($since -lt $SilentRetrySeconds) {
                continue
            }
        }
        Write-Log "$port を ${ProbeSeconds}s 読んで rt-usb か確認する"
        $code = Invoke-RtProbe -Port $port
        if ($code -eq 0) {
            $null = $script:silentAt.Remove($port)
            if (Start-DevM5 -Port $port) {
                $script:starting = $true
                $script:startAt = Get-Date
                $script:pageOpened = $false
            }
            return
        }
        if ($code -eq 1) {
            $script:silentAt[$port] = Get-Date
            Write-Log "$port に rt-usb のフレームが無い。ダウンロードモードならこのまま書き込める。次の確認は ${SilentRetrySeconds} 秒後"
            continue
        }
        Write-LogOnce "$port は他のプロセスが開いている。Hub は起動しない"
    }
}

# ログオンと登録の両方が起動しても、監視は 1 本にする。
$mutex = New-Object System.Threading.Mutex($false, "Local\YuukiLabUsbHubWatch")
$owned = $false
try {
    $owned = $mutex.WaitOne(0)
} catch [System.Threading.AbandonedMutexException] {
    $owned = $true
}
if (-not $owned) {
    exit 0
}

try {
    Write-Log "監視を開始した"
    while ($true) {
        try {
            Invoke-WatchStep
        } catch {
            Write-Log $_.Exception.Message
        }
        Start-Sleep -Seconds 1
    }
} finally {
    if ($owned) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
