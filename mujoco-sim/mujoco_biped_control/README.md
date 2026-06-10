# mujoco_biped_control

MuJoCo 上の **明示制御（非 RL）** による両脚歩行実験です。  
`mujoco_rl_sim` とは別パッケージで、RL の checkpoint / PPO には依存しません。

## 構成

| パス | 内容 |
|------|------|
| [walk_v0/](walk_v0/) | 第 1 実験 — 制御プログラム + ログ + 可視化 |

## MuJoCo モデル

**exp_030** と同一の `model/main.xml`・物理（50 Hz 制御・12 DOF action）を利用します。  
シミュレータ本体は exp_030 の `EnvBipedPPO` を **評価・ログ用途** で再利用します（学習は行いません）。

## AI 改善ループ向け

1. `controller/walk.py` または `conf/controller.yaml` を編集  
2. `python run.py` で走行（**seed 固定**）  
3. `runs/.../trajectory.csv` / `incidents.json` / `summary.json` を分析  
4. `replay_incident.py` で問題瞬間を viewer / PNG で確認  
5. 再実装

## クイックスタート

```bash
cd mujoco-sim/mujoco_biped_control/walk_v0
pip install -r requirements.txt
python run.py
python visualize.py
python replay_incident.py --run-dir ../../runs/mujoco_biped_control/walk_v0/run_YYYYMMDD_HHMMSS --incident-index 0
```

成果物: `mujoco-sim/runs/mujoco_biped_control/walk_v0/`
