# USB プロトコル

仮想 COM（USB CDC）のまま、中身だけバイナリです。WinUSB 専用ドライバは不要です。115200 は CDC ではほぼ飾りです。

旧 ASCII（`#S,...` など）との互換はありません。ファーム `kUsbFwVer = 10` と Python `FW_VER = 10` を揃えます。

正本:

- ファーム: `src/rt_usb/usb_proto.hpp`
- Python: `tools/lib/rt_usb_proto.py`

## フレーム

```text
0xAA 0x55 | type | len_lo | len_hi | payload[len] | crc16_le
```

- マジック `AA 55` で同期。USB FS は 64 バイトで切るので、受信側は状態機械で組み立てる
- `len` は LE uint16。payload 最大 512。ver=10 で 255 を超えるテレメトリを載せるため
- CRC-16-CCITT、初期値 `0xFFFF`。範囲は **type + len16 + payload**（マジックは含めない）
- オーバーヘッド 7 バイト。テレメトリ payload は **316 バイト**（8 関節 × 8 INA + 足 4 隅）

種類の番号: ボード→PC は `0x01…`、PC→ボードは `0x80…`。

## PC → ボード

| type | 名前 | 意味 |
|---|---|---|
| `0x80` | Ping | 識別。未スキャンなら SCAN も |
| `0x81` | Scan | I2C トポロジ |
| `0x82` | Identify | LED を約 2.5 秒虹色 |
| `0x83` | Hold | Lab は PWM オフ。Robot は 135° |
| `0x84` | CalAbort | 校正中断 |
| `0x85` | Cal | 軸の掃引校正（ファーム側。いまの GUI は PC 掃引が多い） |
| `0x86` | Mode | Lab=0 / Robot=1 |
| `0x87` | Out | 軸の PWM 許可。ch=`0xFF` は全軸 |
| `0x88` | Joint | Lab の手動角（許可軸のみ） |
| `0x89` | Probe | Grove 直結 or Hub+CH を 1 回読む |
| `0x8A` | ProfGet | 関節プロファイル要求 |
| `0x8B` | ProfDefault | 既定配線に戻して NVS 保存 |
| `0x8C` | ProfPut | 全軸 + 足経路を 1 メッセージで NVS へ |
| `0x8D` | MapGet | 校正マップをチャンク送出 |
| `0x8E` | MapChunk | マップ書き込み。start=0 で開始、末尾で commit |

## ボード → PC

| type | 名前 | 意味 |
|---|---|---|
| `0x01` | Telemetry | 20 Hz スナップショット |
| `0x02` | Hello | `ver, mode, joints, ina, servo, out_mask` |
| `0x03`…`0x05` | Scan* | トポロジの開始 / ノード / 終了 |
| `0x06`…`0x08` | Prof* | プロファイル本体 / OK / 失敗 |
| `0x09`…`0x0B` | Map* | マップチャンク / OK / 失敗 |
| `0x0C` | Mode | モードと out_mask |
| `0x0D`…`0x10` | Cal* | 校正の開始 / 進捗 / OK / 失敗 |
| `0x11` | EvtOc | 過電流で PWM 停止 |
| `0x12` | EvtBtn | 本体ボタン（Identify も開始） |
| `0x13` | IdentifyOk | Identify 開始 |
| `0x14` | Probe | AS5600 / INA / なし |

HELLO の `ina` は **監視枠の数**（現状 8）であり、刺さっている台数ではありません。欠測は文字列 `nan` ではなく `ok=0` + ダミー 0。失敗理由は `UsbReason` の数値です。

マップは 16 点ずつチャンクします。受信中はテレメトリ送信を止めて取りこぼしを防ぎます。

## Hub から見たとき

ブラウザが送るのは Socket.IO の JSON（例: `{ op: "hold" }`）です。`lab_debug.py` の `apply_op()` が同じ入口で USB フレームに落とします。iPad でも PC Chrome でも、ブリッジに繋がると Tk 側のロボット操作は表示のみになります（全停止と USB 接続は残る）。
