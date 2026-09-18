# USB プロトコル

仮想 COM（USB CDC）のまま、中身だけバイナリです。WinUSB 専用ドライバは不要です。デバイスマネージャに COM が出ます。`115200` は CDC ではほぼ飾りで、実速度は USB Full Speed（12 Mbps、パケット 64 バイト）です。

旧 ASCII（`#S,...` など）との互換はありません。ファーム `kUsbFwVer` と Python `FW_VER` を揃えます（いま **14**）。

正本:

- ファーム: `src/rt_usb/usb_proto.hpp`
- Python: `tools/lib/rt_usb_proto.py`

## プログラムから見た中身

ターミナルや `pio device monitor` が期待する「行指向の文字」ではありません。COM に流れるのは **バイト列** です。先頭がしばしば `AA 55` なので、テキストとして開くと化けます。解釈は `rt_usb_log.py` か Hub に任せます。

USB は半二重の RS-232 ではありません。ホストとデバイスは同時に送れます。ただし **CDC のパイプは 1 本**なので、20 Hz テレメトリと巨大な NVS ダンプは同じ出口を奪い合います。

受信側は 64 バイトごとに切れた塊を、マジックと長さと CRC でフレームに戻します。欠けたら捨てて次の `AA 55` を探します。

## フレーム

```text
0xAA 0x55 | type | len_lo | len_hi | payload[len] | crc16_le
```

- マジック `AA 55` で同期。CRC には入れない
- `len` は LE uint16。payload 最大 512。ver=10 で 255 を超えるテレメトリを載せるため
- CRC-16-CCITT、初期値 `0xFFFF`。範囲は **type + len16 + payload**
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
| `0x8C` | ProfPut | 全軸 + 足 + **有効 2 バイト**。長さ不足は拒否 |
| `0x8D` | MapGet | 校正マップをチャンク送出（この間テレメトリ停止） |
| `0x8E` | MapChunk | マップ書き込み。start=0 で開始、末尾で commit |
| `0x8F` | NvsList | パーティションのキーを送出。値も載せる（重い） |
| `0x90` | NvsErase | 名前空間 `cal` または `jprof` だけ消せる |

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
| `0x15` | NvsBegin | 一覧開始 |
| `0x16` | NvsEntry | 名前空間・キー・型・サイズ |
| `0x17` | NvsEnd | 件数と合計バイト。これが来ないと Hub は未読取 |
| `0x18` | NvsData | 値の断片（hdr + 最大 192 B） |

HELLO の `ina` は **監視枠の数**（現状 8）であり、刺さっている台数ではありません。欠測は文字列 `nan` ではなく `ok=0` + ダミー 0。失敗理由は `UsbReason` の数値です。

Prof 本体の末尾 2 バイトが関節マスクと足です。ver 13 未満のファームはマスクを落とします。

マップは 16 点ずつチャンクします。受信中はテレメトリ送信を止めて取りこぼしを防ぎます。**この一時停止があるので、校正マップは CDC で運べます。** NVS 全文ダンプはまだテレメトリと同居しているので、同じ大きさでも落ちます。

## Hub から見たとき

ブラウザが送るのは Socket.IO の JSON（例: `{ op: "hold" }`）です。`lab_debug.py` の `apply_op()` が同じ入口で USB フレームに落とします。iPad でも PC Chrome でも、ブリッジに繋がると Tk 側のロボット操作は表示のみになります（全停止と USB 接続は残る）。

イベントは接続時に `m5/events` で最大 5000 行のスナップショット、以降は `m5/events/append` で増分だけです。画面は新しい行を下に足します。
