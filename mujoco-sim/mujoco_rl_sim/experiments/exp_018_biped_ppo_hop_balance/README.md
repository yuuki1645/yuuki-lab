# exp_018: 両脚ロボット向け PPO（exp_017 fork）

## 概要

[docs/images/robot_front.jpg](../../../../docs/images/robot_front.jpg) に近い、**現実の両脚のみのバイペッド**を MuJoCo でシミュレートし、強化学習を行う実験。

- **片脚ホッパ系（exp_017 以前）とは別系統**
- コード・報酬・観測は **exp_017 のコピー**（両脚 XML 確定後に合わせて調整予定）
- **`model/main.xml`** — `docs/robot_spec.md` と設計図に基づく両脚モデル（10 DOF）

## 仮説（初期）

exp_017 と同様、報酬バランス（前進↓・進捗/押し出し/着地↑）を出発点とする。両脚 XML 確定後、観測次元・関節数・報酬項をバイペッド向けに更新する。

## 変更（exp_017 比）

| 項目 | exp_017 | exp_018 |
|------|---------|---------|
| ロボット | 片脚ホッパ | **両脚バイペッド（目標）** |
| 報酬係数 | 同左 | **同左（コピー）** |
| XML | 片脚 main.xml | **両脚 10-DOF（docs/robot_spec 準拠）** |

## 学習

```bash
cd mujoco-sim
python -m mujoco_rl_sim.experiments.exp_018_biped_ppo_hop_balance.train
```

※ 観測・行動は exp_017（2-DOF）のまま。**学習前に両脚向けの Python 更新が必要**。

## モデル確認

```bash
cd mujoco-sim
python -c "import mujoco; m=mujoco.MjModel.from_xml_path('mujoco_rl_sim/experiments/exp_018_biped_ppo_hop_balance/model/main.xml'); print('nu', m.nu)"
```

## 結果

| checkpoint | dx_pol | 備考 |
|------------|--------|------|
| （学習後に記入） | | |
