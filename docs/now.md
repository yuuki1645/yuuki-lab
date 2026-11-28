# いまの方針

等身大二足の現行だけを書く。関節の中立とプラスの向きは [joint_angles.md](joint_angles.md)。寸法と重量は [robot_spec.md](robot_spec.md)。手順の入口は [isaac-lab/README.md](../isaac-lab/README.md)。

意味を変えるときは、このページと、ページが指しているコードを同じ変更で直す。数値の表はここへ写さない。

## 本線

学習は Isaac Lab の `YuukiLab-BipedWalk-v0`、再生は `YuukiLab-BipedWalk-Play-v0`。仕様は `isaac-lab/source/yuuki_isaac_lab/yuuki_isaac_lab/tasks/manager_based/biped_walk/biped_walk_env_cfg.py`。

機体は `yuuki_legs_cfg.py` の `FUSION_LEGS_CFG`。形状は `fusion-urdf-export/BipedAssembly_description/urdf/BipedAssembly.urdf`。カゴは地面に固定しない。自己衝突は切る。股のホーンと骨盤が重なって跳ねるため。

書き出した URDF は手で直さない。角度、軸、トルク、速度は `fusion2URDF/core/yuuki_joint_names.py` の `apply_yuuki_servo_limits` が次の書き出しで入れる。ディスク上の `effort` と `velocity` が初期値のままでも、学習のアクチュエータ設定が先に効く。

チェックポイントは、起動したディレクトリの `logs/rsl_rl/yuuki_biped_walk/`。これまでの Fusion 学習はリポジトリ直下にある。

学習と再生は、リポジトリ外の Isaac Lab 3 の `isaaclab.bat` で起動する。conda の Python は使わない。

## 箱モデルと以前の実験

`robot_description/yuuki_biped.urdf` と `YUUKI_LEGS_CFG` は、手動の踵操作だけに使う。歩行の学習には使わない。

MuJoCo の exp_030 以前は、以前の実験である。新しい学習の仕様にはしない。

## 実機との交互

最終目標は、この学習で現実の等身大の脚を動かすこと。学習と実機のデータ取りは交互に行い、分布の違いとバグを早く見つける。最初の実機データは直立で、自由な歩行はその前の確認が合うまで行わない。手順は [sim_to_real.md](sim_to_real.md)。

実機に載せる方策は、学習 `2026-11-27_14-01-29_stand_half` の `model_2200`。重みは `core-rt/src/policy_weights.hpp`。推論は腰の CoreS3 で、周期は約 33 ms。スイッチは実機テレメトリの「方策」ボタン（USB `0x92`）。起動時は切、最初の前進指令は 0。書き込みはサブ PC。

方策の 1 周期は USB `0x1A`。自動記録の take にも `policy/` として残り、関節の並びと単位は同じフォルダの `context.json` に入る。正本は [link/schema/core_take_v2.md](../link/schema/core_take_v2.md)。再生の方策ステップは、同じ `storage.yaml` の `sim/` 以下へ自動で残す。形式は `sim_play_v1`。正本は [link/schema/sim_play_v1.md](../link/schema/sim_play_v1.md)。開いている断片は NAS へ送らない。画面の分布比較は、記録開始の `policy_trace.jsonl` と、再生のローカル側を読む。手順は [sim_to_real.md](sim_to_real.md)。方策の目標は、初期の可動で先に止める。数値は `core-rt/src/walk_policy.cpp` の `clampPolicyDeg`。そのあと、前進 0 で直立から外れた状態が続くとネットを止める。危険な目標は腰の周期の中で速度を抑え、範囲の外が続くと直立へ戻す。サブ PC で続けるときの判断は [sub_pc.md](sub_pc.md)、メイン PC でシミュの観測と出力を見るときの判断は [main_pc.md](main_pc.md)。どちらも作業が終わったら消す。

## Hub

関節の度とラジアンは `robot_description/hub_link.py` だけが変換する。画面のプラスは URDF のプラス。直立の 0 rad は、RDS51150 なら画面の 135°、SM105BL なら画面の 0°。

歩行再生は `isaac_hub_bridge.py` の Socket.IO `:8795` と、Isaac との TCP `:8796` を使う。実機の `lab_debug.py`（`:8794`）とは同時に使わない。
