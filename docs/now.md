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

## Hub

関節の度とラジアンは `robot_description/hub_link.py` だけが変換する。画面のプラスは URDF のプラス。直立の 0 rad は、RDS51150 なら画面の 135°、SM105BL なら画面の 0°。

歩行再生は `isaac_hub_bridge.py` の Socket.IO `:8795` と、Isaac との TCP `:8796` を使う。実機の `lab_debug.py`（`:8794`）とは同時に使わない。
