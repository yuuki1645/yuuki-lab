# 関節角の正本

二足の10関節について、中立、プラスでどちらへ曲がるか、どの範囲が実機の窓かをここに書く。寸法と重量は [robot_spec.md](robot_spec.md)、配線は [core-rt の topology.hpp](../core-rt/src/topology.hpp) です。

画面のプラスは URDF のプラスです。直立のとき URDF は 0 rad です。RDS51150 は画面の 135°、SM105BL は画面の 0° が、その 0 rad です。左右でプラスの意味は同じです。

意味を変えるときは、この表と、表が指している定数を同じ変更で直します。

## 10関節

チャンネルは両脚とも上から股ロール、股ピッチ、ひざ、かかとピッチ、かかとロールです。右が 0〜4、左が 5〜9 です。

| 関節 | 右 / 左 | URDF | サーボ | 中立 | 実機が受け付ける範囲 | 画面の範囲 | 中立よりプラス |
|---|---|---|---|---|---|---|---|
| 股ロール | 0 / 5 | `right_hip_roll` `left_hip_roll` | RDS51150 | 135° | 40〜230° | 100〜170° | 脚を外側へ開く |
| 股ピッチ | 1 / 6 | `right_hip_pitch` `left_hip_pitch` | RDS51150 | 135° | 40〜230° | 100〜170° | 脚を前へ出す |
| ひざ | 2 / 7 | `right_knee_pitch` `left_knee_pitch` | SM105BL ID 1 / 3 | 0° | −30〜150° | 同じ | 後ろへ曲げる |
| かかとピッチ | 3 / 8 | `right_ankle_pitch` `left_ankle_pitch` | SM105BL ID 2 / 4 | 0° | ±60° | 同じ | つま先を上げる |
| かかとロール | 4 / 9 | `right_ankle_roll` `left_ankle_roll` | RDS51150 | 135° | 40〜230° | 100〜170° | 内側が下がる |

股ピッチのプラスは、いまの Robotics Hub と Isaac Sim で脚が前へ出る向きです。箱モデルの「ピッチのプラスは後ろ」は、この表には使いません。

## 数値を持っているコード

角度の意味はこの文書、度の数値は動いているコードです。

| 意味 | コード |
|---|---|
| 135° と 0°、チャンネル順、度とラジアン | `robot_description/hub_link.py` |
| RDS の 40〜230°、SM105 の −30〜150° と ±60° | `core-rt/src/main.cpp` の `clampMove` と `clampSms` |
| 画面の RDS 100〜170° | `robotics-hub/src/features/m5-telemetry/rightLeg.ts` の `SERVO_MIN_DEG` / `SERVO_MAX_DEG` |
| 左かかとピッチだけ、サーボのカウントが増える向きが逆 | `core-rt/src/sms_link.cpp` の `smsDirection`。画面に届く前に、プラスをつま先上げへ揃える |
| 左股ロール、両ひざ、左かかとロールの URDF 軸を反転 | `fusion2URDF/core/yuuki_joint_names.py` の `_SERVO_NEGATIVE_Z`。左右で上の表と同じプラスになる |

Fusion から書き出した URDF では、股ピッチの軸は反転しません。書き出し後の +Z が、すでに「脚を前へ出す」向きです。

Robot モードの保持は、RDS が 135°、SM105BL が 0° です。`main.cpp` の起動時に `gCmd` へその値を入れます。

## この表の範囲ではないもの

次の数字は実機の窓ではありません。

| 場所 | 中身 |
|---|---|
| `fusion-urdf-export/BipedAssembly_description/urdf/BipedAssembly.urdf` の `<limit>` | 書き出しの初期値。いまは全関節 ±0.698 rad（±40°） |
| `robot_description/yuuki_biped.yaml` の `joints_deg` | 箱モデルの仮の学習範囲。股ロール ±45°、股ピッチ −45〜90°、ひざ 0〜120°、かかとピッチ ±45°、かかとロール ±30° |
| 箱モデルのピッチ軸 +Y | 右手系なので、この URDF の正のピッチは脚を後ろへ曲げる。実機の股ピッチ（プラスで前）とは逆 |

箱モデルは `python robot_description/generate_urdf.py` の生成物です。Fusion の `BipedAssembly.urdf` とは別のロボット記述です。
