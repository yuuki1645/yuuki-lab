# exp_019: 両脚バイペッド前進 PPO（10 DOF・テレメトリ）

## 概要

**exp_018 と同一の学習**（観測 42 / 行動 10 / 報酬 shaping）に加え、次を既定で有効にします。

- **現実時間ステップ**（50 Hz、`STEP_WALL_SLEEP_SEC = CONTROL_TIMESTEP_S`）
- **学習中 MuJoCo ビューア**（同期レートも制御周期に合わせる）
- **robotics-hub テレメトリ**（Socket.IO `rl_telemetry/*`、既定ポート **8791**）

## 学習

```bash
cd mujoco-sim
python -m mujoco_rl_sim.experiments.exp_019_biped_ppo_hop_balance.train
```

高速学習のみ（ビューア・実時間待ちオフ）:

```bash
python -m mujoco_rl_sim.experiments.exp_019_biped_ppo_hop_balance.train --no-viewer --step-wall-sleep 0
```

## テレメトリ（robotics-hub）

1. 上記 `train` を起動（`[telemetry] Socket.IO http://0.0.0.0:8791` が表示される）
2. robotics-hub の **テレメトリ**（`/telemetry`）を開く
3. 学習ストリームが `biped_ppo_v1` スキーマで観測・行動・報酬を表示する

`step-wall-sleep` スライダーで壁時計待ちを変更可能（ビューア有効時は visualize の sleep が優先）。

## 可視化

```bash
python -m mujoco_rl_sim.experiments.exp_019_biped_ppo_hop_balance.visualize
python -m mujoco_rl_sim.experiments.exp_019_biped_ppo_hop_balance.visualize --checkpoint runs/.../latest.pt
```

## exp_018 との違い

| 項目 | exp_018 | exp_019 |
|------|---------|---------|
| 学習本体 | 同一 | 同一 |
| 既定ビューア | オフ | **オン** |
| 既定 step 速度 | 最大 | **実時間** |
| Hub テレメトリ | なし | **あり（biped_ppo_v1）** |
