# sim_play_v1

Isaac Lab の再生 `YuukiLab-BipedWalk-Play-v0` が、方策ステップごとに残す記録です。実機の `core_take_v2` ではありません。USB のセンサや指令は入りません。

このファイルは take フォルダの `schema.md` です。機械が読む契約は同じフォルダの `context.json` です。関節の並び、38 個の名前、目標角の意味はそちらを正にしてください。`meta.json` の `format_id` が `sim_play_v1` のとき、この説明と対応します。

実験名（直立、1関節、体重移動、浅いしゃがみ）は `context.json` の `experiment` と `meta.json` の `name` にあります。実機の自動記録には実験名がありません。実機と並べるときは、時刻ではなく実験名で分布を比べます。

## フォルダ

```text
sim/年/月/日/003_130102/
  schema.md
  context.json
  meta.json
  policy/part-000.jsonl
```

親はユーザーの `storage.yaml` です。実験中の正本は `data_root` の下、閉じたファイルの写しは `archive_root` の下です。`storage.yaml` が無い PC では、リポジトリの `atom-rt/data/policy_traces/sim/` にだけ残ります。

フォルダ名は `連番_時分秒` です。連番はその日の再生 take の何本目かで、1 始まりです。実機 take の連番とは別です。消した番号は詰めません。

`part-000` から番号順に繋げたものが、その take の時系列です。1 断片は約 60 秒です。空の断片は残しません。開いている断片は、閉じるまで保管先にありません。実験名が変わったときと、再生プロセスが終わったときにも、開いている断片を閉じます。

## policy/part-NNN.jsonl

再生が方策を 1 周期進めるたびに 1 行です。画面へ出している 20 Hz ではなく、方策のステップです。観測は `obs_buf` の policy そのもので、画面の度からは作りません。

配列の並びは方策の関節順です。画面の右 0〜4、左 5〜9 ではありません。名前は `context.json` の `policy_joints` と `policy.obs` です。

| 欄 | 意味 |
|---|---|
| `t` | 再生を動かしている PC の UNIX 秒。実機 take の `t` とは合わせない |
| `seq` | この再生の中の番号 |
| `t_period_us` | シミュの方策周期（マイクロ秒） |
| `obs` | ネットへ入れた 38 個。欠測は `null` |
| `action` | ネットの生出力。長さ 10。ガウス分布からは引かない |
| `action_rad` | `action` に `context.json` の `action_scale` を掛けた、直立からの目標（ラジアン）。頭打ちの前 |
| `cmd_rad` | Isaac Lab が関節へ渡した目標。直立 0 rad に、生出力へ `action_scale` を掛けた値を足したもの。方策の関節順 |

再生の `action_rad` と `cmd_rad` は、どちらも頭打ちの前です。実機の速度制限と、前進 0 のあいだの包絡は、このファイルにはありません。ネットが欲しかった角度は `action_rad` を見ます。

`joint_flag`、`safety`、`foot_bearing`、`age_ms` は、実機の `policy/` と同じ欄です。再生では関節と IMU の欠測は無く、`safety` は 0 です。`foot_bearing` は、その周期の足裏を分布の平均に入れてよいかです。

## context.json

この take を、リポジトリを開かずに解釈するための契約です。記録を開いた時点の写しなので、あとから学習を変えても、このファイルは書き換わりません。

| 欄 | 意味 |
|---|---|
| `format_id` | `sim_play_v1` |
| `experiment` | 直立、1関節、体重移動、浅いしゃがみのいずれか |
| `project` | 再生タスク、学習 run、チェックポイント |
| `policy_joints` | 方策の関節順 |
| `policy.obs` | 38 個の名前。添字は `obs` の並び |
| `policy.action_scale` | `action_rad = action * action_scale` の係数 |
| `policy.action_rad` | 頭打ち前の直立からの目標 |
| `policy.cmd_rad` | シミュが関節へ渡した目標。実機の包絡は通っていない |

## meta.json

| 欄 | 意味 |
|---|---|
| `format_id` | `sim_play_v1` |
| `id` | 画面が 1 本を指す名前。`年月日_連番_時分秒` |
| `name` | 実験名 |
| `side` | `sim` |
| `sample_count` | 書いた行数 |
| `recording` | まだ再生が書いているあいだ true |
| `open_parts` | 開いている断片。閉じると空 |
