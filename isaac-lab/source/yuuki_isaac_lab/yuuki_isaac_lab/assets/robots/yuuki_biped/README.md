# yuuki_biped

Isaac Lab 用の両脚ロボット資産（**USD 一本化**）。

## レイアウト

```
yuuki_biped/
├── yuuki_biped_cfg.py   # YUUKI_BIPED_CFG (UsdFileCfg)
├── usd/
│   ├── yuuki_biped.usd              # spawn 用エントリ
│   └── configuration/               # instanceable 部品
└── README.md
```

## 編集方針

- 形状・関節・見た目の正本は `usd/yuuki_biped.usd`（および `configuration/`）。
- Isaac Sim で開いて編集するか、USD ツールで更新する。
- タスク側（報酬・観測）はボディ名 / 関節名（例: `basket_thigh`, `left_knee_pitch`）に依存する。名前を変えたら MDP も合わせて更新する。

## Articulation root

USD 内に `worldBody` と `basket_thigh` の 2 つの ArticulationRoot があるため、
`YUUKI_BIPED_CFG.articulation_root_prim_path` でロボット本体を明示している。

```
/basket_thigh/basket_thigh   # relative to spawned .../Robot prim
```

（USD ファイル内では `/main_isaac/...` だが、spawn 時に defaultPrim が剥がれて上記になる）
