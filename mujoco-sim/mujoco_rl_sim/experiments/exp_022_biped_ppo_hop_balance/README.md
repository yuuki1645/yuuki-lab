# exp_022: 足裏 25 cm 両脚バイペッド PPO（contact 走査なし）

exp_021 と同一モデル・学習設定。**`data.contact` 走査と接触終了を削除**した性能 ablation。

| 項目 | exp_021 | exp_022 |
|------|---------|---------|
| 足裏板 | 25 cm | 25 cm（同一 XML） |
| 接触終了（バスケット/大腿/すね） | あり | **なし** |
| すね step ペナルティ | あり | **なし** |
| stance / aerial 判定 | geom 接触 | **IMU 高さ**（`STANCE_IMU_Z_THRESHOLD`） |
| 観測 foot_contact (dim 8–9) | ±1（接触） | **常に -1**（契約維持・未使用） |

## 学習

```bash
cd mujoco-sim
python train.py --no-viewer --step-wall-sleep 0
```

並列起動:

```powershell
.\launch_parallel.ps1
```

## 終了条件（姿勢のみ）

| 条件 | 理由 | ペナルティ |
|------|------|-----------|
| `imu_z < 0.40 m` | `imu_z` | **−30** |
| `upright < 0.52` | `low_upright` | **−30** |
| `imu_zaxis_x < −0.38` | `backward_lean` | **−30** |

詳細は exp_021 の README を参照（接触終了の節は exp_022 では無効）。
