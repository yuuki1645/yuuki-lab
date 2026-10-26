#requires -Version 5.1
<#
.SYNOPSIS
  ATOM / CoreS3（VID 303A）が 1 本見えたら robotics-hub を起動し、版に合う画面を開く。

.NOTES
  このプロセス自身は COM を握り続けない。確認は usb_rt_probe.py が短時間読むだけ。
  机の rt-usb（ver 14、probe の bench）は /atom-bench。
  腰の CoreS3（ver 15、probe の core）は /m5-telemetry。
  判別できないフレームは実機テレメトリを開く。ケーブルは 1 本の想定。
  Hub と lab_debug.py は、rt-usb のフレームが見えたときだけ npm run dev:m5 で起動する。
  ケーブルを抜いても Hub は止めない。実験の途中でプロセスを落とさないため。
  時計の横にアイコンを出す。右クリックでログと、この監視だけの終了。
  ログは %LOCALAPPDATA%\yuuki-lab\usb_hub_watch.log。
#>

$ErrorActionPreference = "Continue"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$HubDir = Join-Path $RepoRoot "robotics-hub"
$Probe = Join-Path $PSScriptRoot "usb_rt_probe.py"
# vite がページを返せるかの確認先。開き先とは分ける。
$HubReadyUrl = "http://127.0.0.1:5173/m5-telemetry"
$HubOrigin = "http://127.0.0.1:5173"
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
# 直近のプローブが書いた 1 語。空のときは実機テレメトリを開く。
$script:probeKind = ""
$script:openUrl = "$HubOrigin/m5-telemetry"
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
        $resp = Invoke-WebRequest -Uri $HubReadyUrl -UseBasicParsing -TimeoutSec 3
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

function Get-HubOpenUrl {
    param([string]$Kind)
    # 机の ver 14 だけ机上ラボ。core も、長さが読めない unknown も実機側。
    if ($Kind -eq "bench") {
        return "$HubOrigin/atom-bench"
    }
    return "$HubOrigin/m5-telemetry"
}

function Invoke-RtProbe {
    param([string]$Port)
    $script:probeKind = ""
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        Write-Log "python が PATH に無い"
        return 2
    }
    # ネイティブの stdout は文字列で受け、戻り値には終了コードだけを残す。
    # ファイルへ > すると Windows PowerShell 5 が UTF-16 で書き、1 語が壊れる。
    $errFile = Join-Path $env:TEMP "yuuki-lab-usb-probe-err.txt"
    $text = & $python.Source $Probe $Port $ProbeSeconds 2> $errFile | Out-String
    $script:probeKind = $text.Trim()
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
    Write-Log "ブラウザを開く $script:openUrl"
    Start-Process $script:openUrl
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

    # 起動待ちのあいだは COM を開かない。lab_debug が掴む前にプローブが競合する。
    if ($script:starting) {
        if (Test-HubPage) {
            $script:starting = $false
            if (-not $script:pageOpened) {
                $script:pageOpened = $true
                Open-HubPage
            }
        } else {
            $elapsed = ((Get-Date) - $script:startAt).TotalSeconds
            if ($elapsed -gt $HubWaitSeconds) {
                Write-Log "Hub が $HubWaitSeconds 秒以内に応答しなかった"
                $script:starting = $false
            }
        }
        return
    }

    # この挿し込みで一度開いたあとは、抜けるまで繰り返さない。
    if ($script:pageOpened -and (Test-HubPage)) {
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
            $script:openUrl = Get-HubOpenUrl $script:probeKind
            Write-Log "$port の画面は $($script:probeKind) → $script:openUrl"
            if (Test-HubPage) {
                # Hub は抜き差しでは止めない。準備済みなら、プローブで決めた URL を開く。
                # 開く前に立てる。ページ確認がメッセージを回すと、タイマーが重なってもう一度開く。
                $script:pageOpened = $true
                Open-HubPage
                return
            }
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

function Update-TrayStatus {
    if (-not $script:trayStatusItem) {
        return
    }
    # メニュー先頭の文言。操作はできない。監視の今をトレイから見るため。
    $text = "待機中"
    if ($script:starting) {
        $text = "Hub を起動しています"
    } elseif ($script:seenAt.Count -gt 0) {
        $text = "ボードを確認しています"
    }
    $script:trayStatusItem.Text = $text
}

function Open-WatchLog {
    # 起動直後に 1 行書いてある。無いときだけ作ってから開く。
    if (-not (Test-Path -LiteralPath $LogPath)) {
        Write-Log "ログを開いた"
    }
    Start-Process -FilePath "notepad.exe" -ArgumentList $LogPath
}

function New-WatchIcon {
    # トレイの絵はスクリプトの隣。差し替えたら、この監視を起動し直すと反映される。
    Add-Type -AssemblyName System.Drawing
    $path = Join-Path $PSScriptRoot "usb_hub_watch.ico"
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Log "アイコンが無い: $path"
        $script:trayIconOwned = $false
        return [System.Drawing.SystemIcons]::Application
    }
    $script:trayIconOwned = $true
    return New-Object System.Drawing.Icon -ArgumentList $path
}

function Stop-WatchTray {
    # Hub の窓は残す。止めるのはこの監視だけ。
    Write-Log "監視を終了した"
    if ($script:trayTimer) {
        $script:trayTimer.Stop()
    }
    if ($script:trayNotify) {
        $script:trayNotify.Visible = $false
    }
    if ($script:appContext) {
        $script:appContext.ExitThread()
    }
}

function Enter-WatchTray {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    [System.Windows.Forms.Application]::EnableVisualStyles()
    $script:appContext = New-Object System.Windows.Forms.ApplicationContext
    $script:trayNotify = New-Object System.Windows.Forms.NotifyIcon
    $script:trayIcon = New-WatchIcon
    $script:trayNotify.Icon = $script:trayIcon
    $script:trayNotify.Visible = $true
    $script:trayNotify.Text = "yuuki-lab USB。挿すと実機テレメトリを開く"

    $menu = New-Object System.Windows.Forms.ContextMenuStrip
    $script:trayStatusItem = $menu.Items.Add("待機中")
    $script:trayStatusItem.Enabled = $false
    [void]$menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
    $openItem = $menu.Items.Add("ログを開く")
    $openItem.Add_Click({ Open-WatchLog })
    $quitItem = $menu.Items.Add("監視を終了")
    $quitItem.Add_Click({ Stop-WatchTray })
    $script:trayNotify.ContextMenuStrip = $menu
    $script:trayNotify.Add_DoubleClick({ Open-WatchLog })

    # 監視は UI と同じスレッド。ポート確認の 1.5 秒だけ、メニューが少し遅れる。
    $script:trayTimer = New-Object System.Windows.Forms.Timer
    $script:trayTimer.Interval = 1000
    $script:trayTimer.Add_Tick({
        # 確認中は止める。Web の待ちがメッセージを回しても、次の確認が割り込まない。
        $script:trayTimer.Stop()
        try {
            Invoke-WatchStep
            Update-TrayStatus
        } catch {
            Write-Log $_.Exception.Message
        } finally {
            if ($script:trayTimer) {
                $script:trayTimer.Start()
            }
        }
    })
    $script:trayTimer.Start()

    try {
        [System.Windows.Forms.Application]::Run($script:appContext)
    } finally {
        if ($script:trayTimer) {
            $script:trayTimer.Stop()
            $script:trayTimer.Dispose()
        }
        if ($script:trayNotify) {
            $script:trayNotify.Visible = $false
            $script:trayNotify.Dispose()
        }
        if ($menu) {
            $menu.Dispose()
        }
        # ファイルから開いたアイコンだけ捨てる。SystemIcons は共有なので触らない。
        if ($script:trayIconOwned -and $script:trayIcon) {
            $script:trayIcon.Dispose()
            $script:trayIcon = $null
        }
    }
}

# トレイは STA でないとアイコンが残らない。スタートアップが忘れていても、ここで起動し直す。
if ([System.Threading.Thread]::CurrentThread.GetApartmentState() -ne [System.Threading.ApartmentState]::STA) {
    $powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $arm = "-NoProfile -Sta -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    Start-Process -FilePath $powershell -ArgumentList $arm -WorkingDirectory $RepoRoot
    exit 0
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
    Enter-WatchTray
} finally {
    if ($owned) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
