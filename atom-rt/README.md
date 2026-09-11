# atom-rt

等身大ロボットの **ATOMS3 Lite**（M5Stack ATOM）用リアルタイム制御ファームと、机上・機体の両方で使う総合デバッグツールです。

本ディレクトリは公開リポジトリ [yuuki-lab](../README.md) の一部です（旧称 `yuuki-lab-robot-side`）。ラズパイ側のサーボ／IMU は [`robot-daemon`](../robot-daemon/README.md)、ブラウザ UI は [`robotics-hub`](../robotics-hub/README.md) です。ATOM の USB はここの `lab_debug.py` が受け、Hub の **実機テレメトリ（M5）**（`/m5-telemetry`）へ Socket.IO（既定 **:8794**）で中継します。

作業は **このディレクトリをカレント** にしてください。

```text
cd atom-rt
pip install -r tools/requirements.txt
python tools/lab_debug.py
```

ファームは **1 本**（環境 `rt-usb`）です。書き込みのたびにスケッチを切り替える必要はありません。机上テストと機体モニタの違いは USB コマンドのモードです。

実験用の CAN・Wi-Fi 校正・複数スケッチは、別リポジトリ `atoms3-as5600-test` に残しています（本リポジトリには含めていません）。

---

## できること

ボード（一度焼けば、以降は Python 側で切り替える）:

- 20 Hz 制御ループ（Core 1）。センサ → 状態 → 政策 → サーボ
- USB テレメトリ（Core 0）。I2C は触らない
- I2C スキャン（PaHub / AS5600 / INA226 / 8Servos）
- 磁石 STATUS と AGC
- Lab（PWM オフ）と Robot（出力オン）
- 軸ごとの PWM 許可と手動指令
- Identify（LED 虹色）。本体ボタンでも GUI 側が反応
- 校正マップの NVS 読み書きと掃引校正（1° マップ作成）
- INA 過電流（既定 8 A）で PWM 停止

PC:

| ツール | 用途 |
|---|---|
| `tools/lab_debug.py` | **総合デバッグ**。複数 ATOM、トポロジ、関節、校正、電源、周期、本記録。接続時（HELLO）に起動アナウンス WAV を再生 |
| `tools/m5_hub_bridge.py` | Hub `/m5-telemetry` 向け Socket.IO 中継（`lab_debug.py` が起動。既定 :8794） |
| `tools/rt_monitor.py` | 1 台の 20 Hz グラフ（従来）。接続時に Robot モードへ切り替える |
| `tools/rt_usb_log.py` | 解釈済みの送受信ログ。キーボードで `ping` / `scan` / `hold` などを送信 |

起動音: `audio/right_leg_boot.wav`（「右脚制御システム起動」）。接続後に異常がなければ続けて `audio/system_all_green.wav` を再生します。判定は HELLO → 初回スキャン → 約 10 フレームで、overrun / 過電流 / 見えている AS5600・INA の欠測が無いこと。ATOMS3R AI Chatbot キットへ移行するまでの暫定で、PC 側 `lab_debug.py` が再生します。Windows の `winsound` を使うため追加パッケージは不要です。

USB は **固定長バイナリフレーム**（マジック + 長さ + CRC）です。旧来の改行 CSV（`#S,...` など）は使いません。GUI とログは解釈結果だけを表示します。

---

## 必要なもの

- PlatformIO Core（`pio`）
- Python 3.10 以降
- `pip install -r tools/requirements.txt`（`pyserial`）
- ATOMS3 Lite
- データ通信できる USB ケーブル

机上では ATOM + 試したい Unit だけで足ります。機体では次が典型です。

```text
ATOMS3 Lite / ATOM S3R Grove I2C
  ├ Unit 8Servos  0x25     Hub 手前
  ├ PaHub 0x70             軸 N = CHN の AS5600（0x36）
  └ PaHub 0x71
       CH0/CH1 = Unit INA226（0x41）。関節プロファイルで 8 枠まで
       CH2     = 右足 ATOMS3 Lite スレーブ 0x28（DF9-40 四隅。経路は変更可）
```

- Grove: SDA=GPIO2、SCL=GPIO1、LED=GPIO35、ボタン=GPIO41
- I2C 100 kHz
- PaHub v2.1 のアドレスは DIP。工場出荷は 0x70。INA 用は 0x71 に合わせる
- 拡張ポートは CH0〜CH5
- サーボ: RDS51150 想定。500〜2500 µs = 0〜270°。指令は **40〜230°**
- INA226: 既定は 10 A ユニット（シャント 5 mΩ）
- 当面 8 軸（`kSnapJoints`）。増やすときは `snapshot.hpp` / `usb_proto.hpp` / `rt_usb_proto.py` を揃える
- INA 監視枠も 8（`kSnapIna`）。未割当は `ina_addr=0` で読まない
- 右足圧スレーブは `FootRoute`（既定 `0x71` CH2 / `0x28`）。`addr=0` で読まない。USB テレメトリは **ver=10**

机上では配線が毎回違って構いません。SCAN が実際に応答したデバイスを返します。

---

## 書き込み

USB CDC です。**lab_debug / rt_monitor / rt_usb_log を開いたままでは書けません。** 書き込み中は ATOM を 1 台だけつなぐのが安全です（モニタはハブで複数可）。

1. Python ツールを閉じる（`pio device monitor` も閉じる）
2. リセットを約 2 秒押し、**緑 LED が点いたら離す**
3. 書き込む:

```text
pio run -t upload
```

既定環境は `rt-usb` だけです（`platformio.ini` の `default_envs`）。このプロトコルは **ver=7** です。焼き直してください。

通信の確認はシリアルモニタではなく:

```text
python tools/rt_usb_log.py
```

`pio device monitor` はバイナリをテキストとして出すので使えません。HELLO の `ver=7` が出れば新しいファームです。

---

## 起動後のモード

| モード | PWM | 政策 | 用途 |
|---|---|---|---|
| **Lab**（焼いた直後の既定） | オフ | 手動指令（出力を許可した軸だけ） | 机上。挿抜、スキャン、磁石確認 |
| **Robot** | 全軸オン | Hold 135° | 機体や、従来の `rt_monitor` |

`rt_monitor.py` は接続すると Robot モードを送ります。モニタを開いただけでサーボが 135° に動きます。机で暴れたくないときは `lab_debug.py` を使い、Lab のままにしてください。

LED（Identify 中以外）:

- 青っぽい … Lab かつ PWM オフ
- 緑 … センサ OK でループに余裕
- 赤点滅 … AS5600 が読めていない
- 赤 … overrun、または Robot なのに 8Servos なし
- 虹色 … Identify 中、または本体ボタン（割当済みなら足 Lite の LED も点灯）

---

## 総合デバッグ `lab_debug.py`

```text
pip install -r tools/requirements.txt
python tools/lab_debug.py
```

iPad から操作するときは、同じ PC で親リポジトリの Hub を起動します。

```text
cd robotics-hub
npm run dev:lab
```

iPad ブラウザで `http://<PCのLAN IP>:5173/m5-telemetry` を開きます。`lab_debug.py` が Socket.IO **:8794** で中継します。iPad 接続中は PC 側のロボット操作は表示のみ（**全停止** と USB 接続／切断は残します）。COM のファイルダイアログ・WAV は PC 専用です。

本記録（センサ＋指令の 20 Hz）は **明示開始〜停止だけ** `data/recordings/` に保存します。Hub のライブラリから一覧・メモ編集・再生（シーク / ±1・5・10 フレーム）できます。REST は同じ :8794 の `/api/m5/recordings` です。

机に複数の ATOMS3 Lite を USB ハブでつなぎ、機体に載せた 1 台にも使えます。

### 画面

- 左: COM 一覧、名前（「机A」「右肩」など）、接続 / 切断 / Identify
- **全接続** … VID `303A`（Espressif）のポートだけ開く
- **全停止** … 全セッションへ HOLD（Lab なら PWM オフ、Robot なら 135°）
- タブ: トポロジ / 関節プロファイル / 関節・試験 / 校正 / 電源 / 周期 / イベント・記録
- 関節プロファイル: 論理軸 → AS5600 / サーボ / INA226 の経路。NVS に書いて焼き直しなしで配線を変えられる
- 校正: 掃引でマップ作成、JSON 保存／読込、NVS へ送信
- 関節・試験: 軸ごとランダム動作。INA の電圧・電流・電力を関節ごとに表示／選択

名前は `tools/lab_nodes.json` に保存します（gitignore 済み）。

### 机上の手順例

1. ファームを焼く（初回、またはファームを更新したときだけ）
2. `python tools/lab_debug.py`
3. COM を選んで接続、または全接続
4. Identify で、机のどの Lite がどの COM か確認（LED が虹色）
5. 「スキャン」で I2C の木を見る。ケーブルを挿すとノードが増える
6. AS5600 なら磁石・AGC。INA なら電圧
7. 木のノードを選んで「1回読む」（制御の 2 軸割り当てとは独立）
8. サーボを動かすときだけ「PWM 出力する」を入れ、スライダで 40〜230°

自動スキャン 5 秒は、挿抜確認用です。機体の 20 Hz を優先するときはオフにしてください。スキャンは制御コアが I2C を使うため、その周期は伸びます。

### 機体の手順例

1. 同じファームのまま載せる
2. `lab_debug.py` で接続し、モードを `robot` にする
   または `rt_monitor.py`（自動で Robot）
3. トポロジが期待どおりか（0x70 の CH0/CH1 に AS5600、0x71 に INA）
4. 追従・電流・周期 overrun を見る

---

## `rt_monitor.py` / `rt_usb_log.py`

従来の 1 台グラフと、解釈済みログです。

```text
python tools/rt_monitor.py
python tools/rt_usb_log.py
python tools/rt_usb_log.py COM11
```

周期・ジッタ・関節角・電力、校正マップのダウンロード / アップロードができます。
Lab 既定のファームでも、`rt_monitor` は Robot にしてから動かす想定です。

`rt_usb_log.py` のキーボード例:

```text
ping
scan
hold
identify
mode lab
mode robot
out 1
out 0 1
cmd 0 135
profget
mapget 0
cal 0
calabort
```

---

## USB プロトコル

USB CDC（仮想 COM）のまま、中身だけバイナリです。WinUSB 専用ドライバは不要です。115200 は CDC ではほぼ飾りです。

旧 ASCII CSV（`#S` / `#PING` など）との互換はありません。ファーム `kUsbFwVer = 9` と `tools/rt_usb_proto.py` の `FW_VER = 9` を揃えます（len が uint16 になったため、旧ファームとは非互換）。

### フレーム

```text
0xAA 0x55 | type | len_lo | len_hi | payload[len] | crc16_le
```

- CRC は type + len16 + payload（CRC-16-CCITT、初期値 0xFFFF）
- len は LE uint16。payload 最大 512 バイト
- 1 フレームを組んでから、できるだけ 1 回の `Serial.write` で出す
- 受信側はマジックと CRC で組み立て／破棄する（USB FS の 64 バイト分割を吸収する）

定義の正本:

- ファーム: `src/rt_usb/usb_proto.hpp`
- Python: `tools/rt_usb_proto.py`

### PC → ボード（type 0x80…）

| type | 意味 |
|---|---|
| Ping | 識別情報。未スキャンならスキャンも |
| Scan | I2C トポロジ |
| Probe | Grove 直結アドレス、または Hub+CH を 1 回読む |
| Mode | Lab / Robot |
| Out | 全軸または軸ごとの PWM 許可 |
| Joint | Lab の手動角（許可軸のみ PWM） |
| Hold | Lab は出力オフ。Robot は 135° |
| Identify | LED を約 2.5 秒虹色 |
| MapGet | NVS のマップをチャンク送出 |
| MapChunk | マップ書き込み（start=0 で開始、最後で commit） |
| ProfGet | 関節プロファイル |
| ProfPut | プロファイル一式を 1 メッセージで書き込み（NVS） |
| ProfDefault | 既定配線に戻して NVS 保存 |
| Cal | 軸の掃引校正 |
| CalAbort | 校正中断（Hold でも中断） |

### ボード → PC（type 0x01…）

| type | 意味 |
|---|---|
| Hello | `ver, mode, joints, ina, servo, out_mask` |
| Telemetry | 20 Hz スナップショット |
| ScanBegin / ScanNode / ScanEnd | トポロジ |
| Mode | モードと out_mask |
| EvtBtn | 本体ボタン（Identify も開始） |
| EvtOc | 電流超過で PWM 停止 |
| Probe | AS5600 / INA / なし |
| MapChunk / MapOk / MapErr | マップ |
| CalStart / CalProg / CalOk / CalErr | 校正スイープ |
| Prof / ProfOk / ProfErr | 関節プロファイル |
| IdentifyOk | Identify 開始 |

HELLO の `ina` は **INA 監視枠の数**（現状 8。関節数と同じ）であり、接続台数ではありません。未割当または未接続なら Telemetry の `ina_ok=0` で、電流・電圧は欠測です。

20 Hz の電源監視は関節プロファイルの `ina_hub / ina_ch / ina_addr` に従い、**全関節枠**を見ます。トポロジで INA226 を選んで関節に割り当てるか、「関節 / 試験」の INA 一覧から選べます。`ina_addr=0` は未割当で、その枠は I2C しません。既定は関節 0〜1 のみ PaHub 0x71 CHi。

欠測は文字列 `nan` ではなく `ok=0` + ダミー 0 です。失敗理由は数値（`UsbReason`）。Python の `REASON` と揃えています。

### 関節プロファイル

論理関節番号と、実際のエンコーダ / アクチュエータ / INA 経路の対応表です。机の配線と機体が違っても **再フラッシュせず** NVS に書けます。`lab_debug.py` の「関節プロファイル」タブ、トポロジの割当、または「関節 / 試験」の INA 一覧から変えられます。

1 メッセージに全軸の `JointRoute`（8 バイト × 軸数）を載せます。

- `hub=0` … Grove 直結（MUX なし）。そのとき `ch` は `-1`
- 既定 … 関節 `i` → AS5600=`0x70` CH`i`（0〜5）、サーボ=手前 `0x25` の ch`i`、INA は関節 0〜1 のみ `0x71` CH`i`。2 軸目以降の INA は SCAN 仮割当またはトポロジから付ける

### 校正スイープ

`lab_debug.py` の「校正」タブ、または Cal コマンド。

1. 関節プロファイルと配線を確認（サーボ・AS5600 が動くこと）
2. 周囲を空けて「校正開始」
3. 40→230→40° を 1° 刻み・静止待ちで往復（数分）
4. 成功すると NVS に保存し、マップチャンクを送出。JSON 保存可
5. 既存 JSON は「JSON を開いて送信」で別ボードへも移せる

中断は「中止」または CalAbort / Hold。

校正マップの JSON 形式（`as5600-servo-map-v1`）は変わりません（`tools/cal_map_io.py`）。`data/cal_map_*.json` を流用できます。

---

## 制御ループ

周期 50 ms（20 Hz）。

1. 要求があれば I2C スキャンまたは PROBE（この周期は長くなり得る）
2. 関節プロファイルに従い AS5600（磁石 + AGC + 角度）を読む
3. 同じプロファイルの INA 経路で INA226（サーボ電源の電圧・電流・電力）を読む
4. 校正マップがあれば unwrap → 指令角へ変換
5. Robot なら 135°、Lab なら手動角
6. プロファイルの `act_*` / `servo_ch` と `out_mask` に従い PWM
7. スナップショットを Core 0 へ

政策（RL）はまだ空で、Robot は Hold です。後から `selectAction` を差し替える想定です。

校正マップの NVS キーは、実験用リポジトリ `atoms3-as5600-test` の `robot` ファームと揃えています。

---

## 安全

- **Lab 既定ではサーボは動かない。** 机ではこのまま使う
- PWM を入れる軸は明示する。可動域 40〜230°
- ボードは INA 電流が約 8 A を超えると全 PWM オフ（`ina_ok` のチャネルだけ）
- `lab_debug.py` にも PC 側の電流閾値（既定 8 A）があり、超えると HOLD。未接続 INA のダミー値では発火しない
- 8Servos の高電圧入力を確認してから出力を許可する
- Identify とスキャンは動きませんが、Robot モードは 135° に保持します

---

## ディレクトリ

```text
platformio.ini
src/as5600.hpp  src/as5600.cpp     角度・磁石・AGC・magnitude
src/robot/pahub.hpp                PCA9548A
src/robot/ina226.hpp               Unit INA226
src/rt_usb/main.cpp                ファーム本体
src/rt_usb/usb_proto.hpp           USB バイナリフレーム
src/rt_usb/joint_profile.hpp       関節経路（NVS / USB）
src/rt_usb/snapshot.hpp            20 Hz 共有データ
tools/rt_usb_proto.py              同じフレームの Python 実装
tools/lab_debug.py                 総合 GUI
tools/m5_hub_bridge.py             Hub / iPad 向け Socket.IO 中継と本記録 REST（:8794）
tools/m5_record_store.py           本記録（data/recordings、明示開始のみ）
tools/rt_monitor.py
tools/rt_usb_log.py
tools/cal_map_io.py
tools/requirements.txt
data/cal_map_*.json            校正マップ（機体・机上）
data/recordings/               本記録（gitignore。明示開始のみ）
audio/right_leg_boot.wav       起動アナウンス
audio/system_all_green.wav     異常なしアナウンス
```

短い WAV（現状約 90 KB、今後 20 本程度）はクローン直後から鳴るように **git に入れます**。合計でも数 MB 程度の想定なので LFS / gitignore は不要です。

`src/robot/` の cpp はコンパイルしません（`build_src_filter` で除外）。ヘッダだけ `rt-usb` と共有しています。

---

## トラブル

| 症状 | 確認 |
|---|---|
| 書けない | ツールを閉じる。緑のダウンロードモード。USB は 1 台 |
| GUI が空 / 壊れた表示 | このディレクトリのファーム（HELLO `ver=7`）か。古い ASCII CSV や ver=6 とは話せない |
| `pio device monitor` が文字化け | 仕様。バイナリなので `rt_usb_log.py` を使う |
| 校正が fit/map で失敗 | 磁石・ギア・干渉。AS5600 がサーボに追従しているか |
| スキャンに出ない | Grove、PaHub DIP、5V。未知アドレスは Hub 先だと既知リスト外のことがある |
| サーボが動かない | Lab のままでないか。PWM チェック。8Servos 0x25。高電圧電源 |
| `rt_monitor` で突然動く | 仕様。接続時に Robot になる |
| COM が PermissionError | 前の Python を残していないか。切断してから数秒待つ |
| 周期 overrun | 自動スキャンを止める。軸・INA が増えると `t_sense` が伸びる |
| 過電流で止まる | メカ干渉・配線。再許可する前に原因を切る。INA 未接続なのに 8 A ならファームを ver=7 に |

複数 ATOM をモニタするときは USB ハブで足ります。**書き込みのときだけ 1 台**にしてください。
