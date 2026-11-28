# core_take_v2

CoreS3（USB ver 15）の実験記録です。腰の CoreS3 が左右の ATOM S3R と両足を CAN で集め、サブ PC が HELLO から USB 切断まで自動で書いています。実験名はありません。方策の 1 周期も、この take に入ります。

このファイルは take フォルダの `schema.md` です。機械が読む契約は同じフォルダの `context.json` です。関節の名前、二つの並び、単位、ネットの出力の意味はそちらを正にしてください。`meta.json` の `format_id` が `core_take_v2` のとき、この説明と対応します。`core_take_v1` のフォルダに `policy/` と `context.json` はありません。

## フォルダ

```text
年/月/日/003_090312/
  schema.md
  context.json
  meta.json
  sensors/part-000.jsonl
  policy/part-000.jsonl
  commands/part-000.jsonl
  events/part-000.log
  gamepad/part-000.jsonl
```

フォルダ名は `連番_時分秒` です。連番はその日の何本目かで、1 始まり、3 桁のゼロ埋めです。時分秒は take を開いたサブ PC のローカル時刻です。消した take の番号は詰めません。日付フォルダの `.last_index` は次の番号を決めるための控で、実験データそのものではありません。

`part-000` から番号順に繋げたものが時系列です。1 断片は約 60 秒です。空の断片は残しません。開いている断片は、閉じるまで保管先にありません。方策の USB が一度も来なかった take では、`policy/` 自体が残りません。

## 時刻

- `sensors`、`policy`、`commands`、`gamepad` の `t` は、サブ PC が受け取った UNIX 秒です。ボードの時計ではありません。
- `sensors` の `seq` と `policy` の `seq` は、別のカウンタです。行を揃えるときは `t` を使います。
- `events` の行頭は、ローカル時刻の ISO 8601（ミリ秒）です。その後ろの `HH:MM:SS` は画面のイベント行に元から付いている時刻です。
- `meta.json` の `started_at` と `ended_at` もローカル時刻の ISO 8601 です。`started_unix` と `ended_unix` は UNIX 秒です。

## 関節の並びは二つある

`sensors` と `commands` の添字は、画面の論理軸です。長さは 10 です。右が 0〜4、左が 5〜9 です。

| 添字 | 脚 | 関節 | サーボ | 直立 |
|---|---|---|---|---|
| 0 | 右 | 股ロール | RDS51150 | 135° |
| 1 | 右 | 股ピッチ | RDS51150 | 135° |
| 2 | 右 | ひざ | SM105BL | 0° |
| 3 | 右 | かかとピッチ | SM105BL | 0° |
| 4 | 右 | かかとロール | RDS51150 | 135° |
| 5 | 左 | 股ロール | RDS51150 | 135° |
| 6 | 左 | 股ピッチ | RDS51150 | 135° |
| 7 | 左 | ひざ | SM105BL | 0° |
| 8 | 左 | かかとピッチ | SM105BL | 0° |
| 9 | 左 | かかとロール | RDS51150 | 135° |

`commands` の `ch` も、関節指令ではこの添字です。プラスの向きは、股ロールが外側、股ピッチが前、ひざが後ろ、かかとピッチがつま先を上げる、かかとロールが内側が下がる、です。左右でプラスの意味は同じです。

`policy` の `obs` の先頭 10 個、`action`、`action_rad`、`cmd_rad`、`joint_flag` は、方策の並びです。左股ロール、右股ロール、左股ピッチ、右股ピッチ、左ひざ、右ひざ、左かかとピッチ、右かかとピッチ、左かかとロール、右かかとロールです。画面の添字への対応は `context.json` の `policy_joints` です。

体の軸は、前が +x、左が +y、上が +z です。方策が見る重力は、直立なら z が約 −1 です。

## sensors/part-NNN.jsonl

1 行が 1 周期です。周期は約 30 Hz です。同じ `seq` は記録時に捨てています。

欠測は `null`、または対応する `*_ok` が false です。0 度や 0 A ではありません。

| 欄 | 意味 |
|---|---|
| `t` | PC 受信の UNIX 秒 |
| `seq` | ファームのテレメトリ周期番号。`policy` の `seq` とは別 |
| `period_us` | 前周期からの間隔（マイクロ秒） |
| `loop_us` | その周期の処理時間（マイクロ秒） |
| `sense_us` | センサー読み取りに使った時間（マイクロ秒） |
| `jitter_us` | `period_us` から目標周期を引いた値（マイクロ秒）。腰の目標は約 33 ms |
| `overrun` | `loop_us` が目標周期を超えた |
| `cmd` | その周期にファームが各軸へ出している指令角（度）。画面の論理軸。エンコーダ角ではない |
| `raw` | AS5600 の角度（度）。およそ 0〜360。欠測は `null` |
| `unwrap` | `raw` の 360 度跨ぎを積算した角度（度）。欠測は `null` |
| `corr` | `unwrap` を校正マップで指令角の空間へ写した角度（度）。欠測は `null` |
| `map_ok` | その軸の校正マップが使える |
| `as_ok` | その軸の角度が読めている。false のとき `raw` `unwrap` `corr` は `null`。ひざとかかとピッチはサーボの現在角 |
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

## policy/part-NNN.jsonl

腰が方策を 1 周期進めるたびに 1 行です。切れている周期も残します。その行の `action` は `null` です。同じ `seq` は記録時に捨てています。

配列の並びは方策の関節順です。画面の右 0〜4、左 5〜9 ではありません。

| 欄 | 意味 |
|---|---|
| `t` | PC 受信の UNIX 秒。`sensors` の `t` と同じ時計 |
| `seq` | 方策トレースの番号。`sensors` の `seq` とは別 |
| `t_period_us` | 前周期からの間隔（マイクロ秒） |
| `t_sense_us` | センサー読み取りに使った時間（マイクロ秒） |
| `t_policy_us` | その周期の方策処理に使った時間（マイクロ秒） |
| `overrun` | 周期が目標を超えた |
| `reason` | なぜその周期になったか。番号の意味は `context.json` の `enums.reason` |
| `reason_text` | `reason` の日本語 |
| `safety` | その周期の安全。0 はなし。1 は速度制限、2 は直立へ戻している、3 は目標を固定 |
| `safety_text` | `safety` の日本語。0 のときは空 |
| `foot_bearing` | 両足の合計が体重を受けているとみなすしきい値以上なら true |
| `dist_ok` | 分布の平均に入れてよい周期なら true。旗が有効で、安全が働いていない |
| `joint_flag` | 長さ 10。0 有効、1 欠測、2 飛び、3 揺れ。方策の関節順 |
| `age_ms` | 長さ 12。方策の関節 10 個のあと、IMU、足裏。その値が何ミリ秒前か。未知は 65535 |
| `obs` | ネットへ入れた 38 個。名前と単位は `context.json` の `policy.obs`。欠測は `null` |
| `action` | ネットの生出力。長さ 10。ガウス分布からは引かない。ネットを回していない周期は要素が `null` |
| `action_rad` | `action` に 0.25 を掛けた、直立からの目標（ラジアン）。頭打ちと速度制限の前。方策の関節順 |
| `cmd_rad` | サーボへ実際に出した目標。直立が 0 rad。方策の関節順。頭打ちと速度制限のあと |

`action_rad` は頭打ちの前です。`cmd_rad` は、前進 0 のあいだ `context.json` の `policy.envelope`（直立からの度、関節ごと）の中に収めたあとです。股とかかとロールは ±20°、ひざは 0°〜+40°、かかとピッチは −20°〜+30° です。計測は `measure_slack_deg`（5°）だけ各側が広く、それを超えて居続けるとネットを止めます。ネットが欲しかった角度は `action_rad`、脚へ出た角度は `cmd_rad` です。`envelope_rad` が 0.35 の古い take は、全関節が約 ±20° だったときの記録です。

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

## gamepad/part-NNN.jsonl

ゲームパッドで踵を動かしたときの操作です。腰は経由しません。`commands` の関節角とは別ファイルです。パッドを起動しなかった take では、このフォルダ自体が残りません。

1 行が積分 1 回です。間隔は約 0.02 秒です。`t` はサブ PC の UNIX 秒で、`sensors` や `commands` と同じ時計です。

| 欄 | 意味 |
|---|---|
| `t` | この行を作った UNIX 秒 |
| `connected` | パッドが挿さっていれば true。抜くと false で、スティックは 0 |
| `homing` | スタートを押していて、全関節 135° の踵へ戻しているあいだ true |
| `left` `right` | 左スティックと右スティック。中身は下の表 |
| `heel_left` `heel_right` | この周期のあとで覚えている踵目標 `[x, y, z]`（m、腰座標）。前が +x、ロボットの右が −y、天井が +z |
| `accepted_left` `accepted_right` | その脚の逆運動学が、この一歩で踵目標を進めたら true。届かない一歩や、入力が無いフレームは false |
| `floor_hold_left` `floor_hold_right` | 接地中なので、その足の床側（−z）だけ捨てたら true |

`left` と `right` の中:

| 欄 | 意味 |
|---|---|
| `forward` | 前後。前が正。デッドゾーンのあと二乗した速度係数で、−1〜1。倒し切りだけ ±1 |
| `lateral` | 左右。ロボットの右が正。同じく二乗した速度係数 |
| `vertical` | 上下。バンパー（天井）が正、トリガー（床）が負。バンパーは約 +0.33、トリガーの倒し切りは −1 |
| `raw_forward` `raw_lateral` | デッドゾーンを掛ける前のスティック。−1〜1 |
| `bumper` | その側のバンパーを押していれば true |
| `trigger` | その側のトリガー。0〜1。デッドゾーン前の読み |

## events/part-NNN.log

画面に出たイベントの文章です。センサーの数値ではありません。1 行が 1 件です。接続、切断、スキャン、欠測、過電流、方策の切り替わり、モード変更が入ります。

## context.json

この take を、リポジトリを開かずに解釈するための契約です。記録を開いた時点の写しなので、あとからファームの定数を変えても、このファイルは書き換わりません。

| 欄 | 意味 |
|---|---|
| `format_id` | `core_take_v2` |
| `project` | 機体、学習 run、チェックポイント、推論の置き場所 |
| `time` | `t` の時計と、二つの `seq` を混ぜないこと |
| `body_frame` | 前が +x、左が +y、上が +z。直立の重力 |
| `firmware_joints` | 画面の論理軸。`sensors` の配列 |
| `policy_joints` | 方策の関節順と、画面の添字への対応 |
| `policy.obs` | 38 個の名前。添字は `obs` の並び |
| `policy.action_scale` | `action_rad = action * action_scale` の係数。現行は 0.25 |
| `enums` | `reason`、`safety`、`joint_flag` の番号 |

## meta.json

| 欄 | 意味 |
|---|---|
| `format_id` | `core_take_v2` |
| `take_id` | フォルダ名。`003_090312` のように連番と時分秒 |
| `day_index` | その日の連番。フォルダ名の先頭と同じ。1 が最初の 1 本 |
| `schema` | この説明のファイル名。通常は `schema.md` |
| `context` | 機械が読む契約のファイル名。通常は `context.json` |
| `recording` | 書き込み中なら true。切断後は false |
| `notes` | あとから人が足すメモ。記録開始時は空 |
| `hello` | 開始時の HELLO 文 |
| `port` | サブ PC の COM ポート名 |
| `fw_ver` | USB の版。この形式は 15 |
| `sample_count` | `sensors` に書いた行数 |
| `policy_count` | `policy` に書いた行数。方策の USB が来なければ 0 |
| `stop_reason` | 閉じた理由。`USB 切断`、`USB エラー`、`ツール終了`、`プロセス終了`、`中断` のいずれか |
| `duration_sec` | 開始から終了までの秒。書き込み中は無い |
