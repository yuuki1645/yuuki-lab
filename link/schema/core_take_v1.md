# core_take_v1

CoreS3（USB ver 15）の実験記録です。腰の CoreS3 が左右の ATOM S3R と両足を CAN で集め、サブ PC が HELLO から USB 切断まで自動で書いています。実験名はありません。

このファイルは take フォルダの `schema.md` です。数値の意味はここを読んでください。`meta.json` の `format_id` が `core_take_v1` のとき、この説明と対応します。

## フォルダ

```text
年/月/日/時分秒/
  schema.md
  meta.json
  sensors/part-000.jsonl
  commands/part-000.jsonl
  events/part-000.log
```

フォルダ名の年月日時分秒は、take を開いたサブ PC のローカル時刻です。同じ秒に重なったときだけ `時分秒_16進4桁` になります。

`part-000` から番号順に繋げたものが時系列です。1 断片は約 60 秒です。空の断片は残しません。開いている断片は、閉じるまで保管先にありません。

## 時刻

- `sensors` と `commands` の `t` は、サブ PC が受け取った UNIX 秒です。ボードの時計ではありません。
- `events` の行頭は、ローカル時刻の ISO 8601（ミリ秒）です。その後ろの `HH:MM:SS` は画面のイベント行に元から付いている時刻です。
- `meta.json` の `started_at` と `ended_at` もローカル時刻の ISO 8601 です。`started_unix` と `ended_unix` は UNIX 秒です。

## 論理軸

配列の添字は論理軸です。長さは 10 です。

| 添字 | 脚 | 関節 |
|---|---|---|
| 0 | 右 | 股ロール |
| 1 | 右 | 股ピッチ |
| 2 | 右 | ひざ |
| 3 | 右 | かかとピッチ |
| 4 | 右 | かかとロール |
| 5 | 左 | 股ロール |
| 6 | 左 | 股ピッチ |
| 7 | 左 | ひざ |
| 8 | 左 | かかとピッチ |
| 9 | 左 | かかとロール |

`commands` の `ch` も、関節指令ではこの添字です。

## sensors/part-NNN.jsonl

1 行が 1 周期です。周期は約 20 Hz です。同じ `seq` は記録時に捨てています。

欠測は `null`、または対応する `*_ok` が false です。0 度や 0 A ではありません。

| 欄 | 意味 |
|---|---|
| `t` | PC 受信の UNIX 秒 |
| `seq` | ファームの周期番号 |
| `period_us` | 前周期からの間隔（マイクロ秒） |
| `loop_us` | その周期の処理時間（マイクロ秒） |
| `sense_us` | センサー読み取りに使った時間（マイクロ秒） |
| `jitter_us` | `period_us` から目標周期（50 ms）を引いた値（マイクロ秒） |
| `overrun` | `loop_us` が目標周期を超えた |
| `cmd` | その周期にファームが各軸へ出している指令角（度）。エンコーダ角ではない |
| `raw` | AS5600 の角度（度）。およそ 0〜360。欠測は `null` |
| `unwrap` | `raw` の 360 度跨ぎを積算した角度（度）。欠測は `null` |
| `corr` | `unwrap` を校正マップで指令角の空間へ写した角度（度）。欠測は `null` |
| `map_ok` | その軸の校正マップが使える |
| `as_ok` | その軸の AS5600 が読めている。false のとき `raw` `unwrap` `corr` は `null` |
| `mag` | 磁石 STATUS。0 正常、1 磁石なし、2 弱い、3 強い、4 I2C 失敗、255 読み飛ばし |
| `agc` | AS5600 の AGC。255 は読み飛ばし |
| `volt` `amp` `watt` | その軸の INA226。単位は V、A、W。読めなければ `null` |
| `ina_ok` | その軸の INA226 が読めている |
| `i2c_err` | 両脚が報告している I2C 失敗回数の合計。1 周期の成否フラグではない |
| `servo_ok` | サーボドライバが応答している |
| `mode` | `lab` または `robot`。起動直後は `lab` |
| `out_mask` | 出力許可。bit N が 1 のとき論理軸 N の PWM が出る |
| `foot` | 右足 |
| `foot_left` | 左足 |

足のオブジェクト:

| 欄 | 意味 |
|---|---|
| `ok` | 足スレーブからサンプルが届いている |
| `seq` | 足スレーブのサンプル番号 |
| `mask` | 装着ビット。bit 0〜3 が四隅 |
| `force_kg` | 四隅の合力（kg） |
| `corners` | 四隅。キーは `top_left`、`top_right`、`bottom_right`、`bottom_left` |

隅が `null` のときは、その隅が無い、または足サンプルが無効です。隅のオブジェクトは `force_kg`（kg）、`force_pct`（定格 2 kg に対する百分率）、`voltage_v`（V）、`rs_ohm`（力への換算に使った抵抗、オーム）です。USB 上の生値はミリボルトで、kg は PC が換算しています。

## commands/part-NNN.jsonl

PC が USB でボードへ送った指令です。`sensors` の `cmd` は、その周期にファームが適用している角度です。送った時刻と適用された周期は別なので、突き合わせは `t` で行います。

| 欄 | 意味 |
|---|---|
| `t` | PC が送った UNIX 秒 |
| `text` | 種類。`CMD` は関節指令、`MODE` は lab/robot、`OUT` は出力許可、ほかに `PING` や `SCAN` など |
| `ch` | 関節指令と出力許可の対象。関節指令では論理軸。出力許可の 255 は全軸 |
| `deg` | 関節指令の角度（度）。`text` が `CMD` のときだけある |
| `mode` | `lab` または `robot`。`text` が `MODE` のときだけある |
| `on` | 出力を出すなら true。`text` が `OUT` のときだけある |

## events/part-NNN.log

画面に出たイベントの文章です。センサーの数値ではありません。1 行が 1 件です。接続、切断、スキャン、欠測、過電流、モード変更が入ります。

## meta.json

| 欄 | 意味 |
|---|---|
| `format_id` | `core_take_v1` |
| `take_id` | フォルダ名の時分秒 |
| `schema` | この説明のファイル名。通常は `schema.md` |
| `recording` | 書き込み中なら true。切断後は false |
| `notes` | あとから人が足すメモ。記録開始時は空 |
| `hello` | 開始時の HELLO 文 |
| `port` | サブ PC の COM ポート名 |
| `fw_ver` | USB の版。この形式は 15 |
| `sample_count` | `sensors` に書いた行数 |
| `stop_reason` | 閉じた理由。`USB 切断`、`USB エラー`、`ツール終了`、`プロセス終了`、`中断` のいずれか |
| `duration_sec` | 開始から終了までの秒。書き込み中は無い |
