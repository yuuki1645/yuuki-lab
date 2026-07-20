# yuuki_biped

Isaac Lab 用の両脚ロボット資産。

- **編集正本**: `urdf/yuuki_biped.urdf`（形状・キネマティクス）
- **実行時資産**: `usd/yuuki_biped.usd`（起動時に毎回変換しない。コミット済み USD を読む）

## レイアウト

```
yuuki_biped/
├── yuuki_biped_cfg.py          # YUUKI_BIPED_CFG (UsdFileCfg)
├── urdf/
│   └── yuuki_biped.urdf        # 編集用（正本）
├── usd/
│   ├── yuuki_biped.usd         # spawn 用エントリ（convert 成果物）
│   └── configuration/          # instanceable 部品
└── README.md
```

## 由来（MJCF → URDF）

`urdf/yuuki_biped.urdf` は、削除済みの Isaac 用 MJCF
`assets/robots/yuuki_biped/main_isaac.xml`（git 履歴）を元に変換した。

変換時の対応:

| MJCF | URDF |
|------|------|
| `box size`（半サイズ） | `box size`（フルサイズ = ×2） |
| joint `range`（度） | `limit`（ラジアン） |
| `freejoint name="root"` | world への fixed なし（浮動ベース） |
| `<site>` | 同名の fixed 子リンク |
| actuator `kp`/`kv` | URDF には含めない（`ArticulationCfg.actuators`） |

## 編集方針

1. **形状・関節・サイト**を変えるときは `urdf/yuuki_biped.urdf` を編集する。
2. 下記の手動手順で **USD を再生成**し、`usd/` をコミットする。
3. リンク名 / 関節名（例: `basket_thigh`, `left_knee_pitch`, `imu_site`）を変えたら、タスク側 MDP も合わせて更新する。
4. PD ゲイン・トルク上限は URDF ではなく `yuuki_biped_cfg.py` の actuators で管理する。

## 手動変換手順（URDF → USD）

Isaac Lab の `convert_urdf.py` を使う。起動のたびに自動変換しないこと。

### 前提

- conda 環境 `env_isaaclab`（または同等の Isaac Lab 環境）が有効
- Isaac Lab リポジトリに `scripts/tools/convert_urdf.py` があること  
  （例: `Z:\Projects\IsaacLab\scripts\tools\convert_urdf.py`）

### コマンド（PowerShell）

```powershell
conda activate env_isaaclab
cd Z:\Projects\yuuki-lab\isaac-lab

# 既存 usd/ を上書きする場合はバックアップ推奨
# Copy-Item -Recurse usd usd.bak

python Z:\Projects\IsaacLab\scripts\tools\convert_urdf.py `
  source\yuuki_isaac_lab\yuuki_isaac_lab\assets\robots\yuuki_biped\urdf\yuuki_biped.urdf `
  source\yuuki_isaac_lab\yuuki_isaac_lab\assets\robots\yuuki_biped\usd\yuuki_biped.usd `
  --headless
```

### フラグの注意

| フラグ | 指定 | 理由 |
|--------|------|------|
| `--fix-base` | **付けない**（デフォルト False） | 浮動ベース。付けるとルートが地面固定になる |
| `--merge-joints` | **付けない** | `imu_site` / foot sites など fixed 子リンクが潰れる |
| `--headless` | 付ける | GUI 不要のバッチ変換 |
| `--joint-stiffness` / `--joint-damping` | 省略可 | 実行時は `YUUKI_BIPED_CFG.actuators` が上書きする |

`convert_urdf.py` のパスはローカルの Isaac Lab クローン位置に合わせて読み替える。

### 変換後の確認

1. `usd/yuuki_biped.usd` と `usd/configuration/` が更新されていること。
2. Isaac Sim / `smoke.py` でスポーンできること。
3. **Articulation root** を確認し、`yuuki_biped_cfg.py` の
   `articulation_root_prim_path` を必要なら合わせる。

現行（MJCF 由来 USD）の設定例:

```
/basket_thigh/basket_thigh   # spawned .../Robot からの相対パス
```

URDF から新規変換すると階層が変わることがある（例: `/yuuki_biped/basket_thigh`）。
その場合は USD を Stage で開き、ArticulationRootAPI が付いている prim を確認してから
`articulation_root_prim_path` を更新する。

4. ボディ名・関節名が MDP（`biped_ppo_walk`）と一致していること。
5. 問題なければ `usd/` を git にコミットする（`urdf/` も合わせてコミット）。

## Articulation root（現行 USD）

USD 内に `worldBody` と `basket_thigh` の 2 つの ArticulationRoot があるため、
`YUUKI_BIPED_CFG.articulation_root_prim_path` でロボット本体を明示している。

（現行ファイル内では `/main_isaac/...` だが、spawn 時に defaultPrim が剥がれて
`/basket_thigh/basket_thigh` になる）
