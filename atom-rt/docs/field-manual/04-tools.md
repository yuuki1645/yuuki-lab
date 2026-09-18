# 道具

PC 側で手を動かす起動物は `atom-rt/tools/` 直下の 3 本だけです。部品は `tools/lib/` にあり、直接起動しません。

## 起動物

| ツール | 用途 |
|---|---|
| `lab_debug.py` | USB デーモン + Hub 中継（:8794）+ 本記録。Tk は非推奨だが機能は残る |
| `rt_monitor.py` | 1 台の 20 Hz グラフ。**接続すると Robot になる**（机では暴れる） |
| `rt_usb_log.py` | 解釈済みの送受信。キーボードで ping / scan / hold など |

起動:

```text
cd atom-rt
pip install -r tools/requirements.txt
python tools/lab_debug.py
```

Hub と同時ならリポジトリの `robotics-hub` で `npm run dev:m5`。リポジトリ直下の `just lab` でも両方上がります。

接続時（HELLO）に `audio/right_leg_boot.wav`、異常がなければ `audio/system_all_green.wav`。判定は HELLO → 初回 SCAN → 約 10 フレームで、overrun / 過電流 / 見えている AS5600・INA の欠測が無いこと。Windows の `winsound` なので追加パッケージは不要です。

Python を直したら **`lab_debug.py` を再起動**します。Hub の再読み込みだけでは COM 側のコードは入りません。ファームを直したら焼き直しです。

COM は 1 プロセスが専有します。PermissionError の多くは、前の Python がポートを残しています。Hub が繋がっているあいだ、同じ COM をシリアルモニタで開けません。

## ライブラリ（`tools/lib/`）

| ファイル | 役割 |
|---|---|
| `lab_app.py` | Tk。USB 操作は `apply_op()`。イベントの append 配信 |
| `lab_usb.py` | ATOM 1 台の COM セッション、起動音。オープン時は DTR を立てない |
| `lab_model.py` | Frame / JointRoute の Python 側 |
| `lab_const.py` | 色・軸数・WAV。イベント上限 **5000** |
| `rt_usb_proto.py` | バイナリフレーム（ファームと揃える） |
| `m5_hub_bridge.py` | Socket.IO と本記録 REST。`m5/events/append` |
| `m5_record_store.py` | `data/recordings/`（明示開始だけ書く） |
| `lab_pc_cal.py` | PC 側の 40→230→40° 掃引 |
| `cal_map_io.py` | JSON `as5600-servo-map-v1` |
| `cop_ankle_ctrl.py` | かかとピッチ COP（再起動で消える） |
| `df9_force.py` | DF9-40 電圧→力 |

本記録はセンサ + 指令の 20 Hz を、記録開始〜停止のあいだだけ残します。Hub のライブラリから再生できます。REST は同じ :8794 の `/api/m5/recordings` です。

シリアルを開くとき pyserial の既定は DTR=true で、ボードがリセットすることがあります。NVS の新規キーを書いている最中だと commit が死にます。`lab_usb.py` は DTR を下げてから開きます。

## Hub の 2 画面

| 画面 | パス | 用途 | ライブ指令 |
|---|---|---|---|
| 実機テレメトリ（M5） | `/m5-telemetry` | 機体（右脚）。記録・カメラ・足圧 | 100〜170° |
| ATOM 机上ラボ | `/atom-bench` | 机上の 1 サーボ。校正・単体テスト | 40〜230° |

ファームは同じ `rt-usb`、中継も同じ `lab_debug.py`（:8794）です。トポロジ・関節プロファイル・NVS・手帳は両方に載せてあります。

机上ラボではトポロジを左カラムに常設しています。画面下端の固定ステータスバーには、接続・USB ver・モード・PWM・指令角・生角・電源・周期・I2C エラーの増分を 20 Hz で出しています。エラーが増えているときだけ赤く点滅します。ver が 13 未満なら有効マスクは使えません。

下のドックはイベントです。新しい行が下、上にスクロールすると追従を止めます。一時停止中は溜めておき、再開でまとめて足します。接続し直すと最大 5000 行のスナップショットが入ります。

タブは URL の `?tab=` です。再読み込みしてもプロファイルや NVS に戻れます。手帳を閉じてもクエリは残します（ハッシュ `#manual/…` だけ消します）。

机上ラボは `joint` / `out` に `wide: true` を付けて送るので、PC 側の 100〜170° クランプを通りません（`clamp_cal_deg`）。

## 校正

いまの総合デバッグは **PC が PWM を握って掃引**し、できたマップを USB で NVS に送ります。40→230→40° を 1° 刻み。JSON は `data/cal_map_*.json` に残せ、別ボードへも移せます。校正マップの正本を PC に置くと、NVS 全文ダンプに頼らなくて済みます。

ファームにも Cal コマンドは残っていますが、GUI の本線は PC 掃引です。Hub からは机上ラボの「校正」タブ、または実機テレメトリの「校正」タブで開始します。

## 安全の読み方

- Lab 既定ではサーボは動かない。机ではそのままでよい
- `rt_monitor.py` を開くだけで 135° に動く。机では使わない
- 書き込みのときだけ ATOM は 1 台。モニタはハブで複数可
- COM の PermissionError は、前の Python がポートを残していることが多い
- 有効を外しても経路は消えない。PWM 許可（out）とは別スイッチ
