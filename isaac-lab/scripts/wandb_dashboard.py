# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""WandB の Workspace（監視ダッシュボード）と Report（監視ガイド）を生成する。

biped_ppo_walk プロジェクト用に、以下の 2 つをプログラムで作成する:

1. **Workspace（Saved View）**: `0_Watchlist/*` の重要指標を最上部セクションに
   まとめた監視画面。学習中はこのビューを開いておけば、見るべき指標だけを
   一目で追える。
2. **Report**: 各指標の意味と「どう推移すると好ましいか」を Markdown で解説し、
   その下にチャートを埋め込んだ共有用ドキュメント（見方の正本）。

前提:
- `pip install wandb-workspaces`（wandb 本体とは別パッケージ）
- `wandb login` 済みであること（学習と同じ認証を使う）

使い方（isaac-lab ディレクトリから）:

    # Workspace と Report を両方作成（既定）
    python scripts/wandb_dashboard.py

    # どちらか片方だけ作成
    python scripts/wandb_dashboard.py --workspace-only
    python scripts/wandb_dashboard.py --report-only

    # entity / project を変える場合
    python scripts/wandb_dashboard.py --entity my-team --project my_project

注意:
- 何度実行しても新しい Saved View / Report が「追加」される（上書きではない）。
  作り直した場合は WandB の UI 側で古い方を削除すること。
- Isaac Sim は不要（純粋な WandB API スクリプト）。
"""

from __future__ import annotations

import argparse

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws

# 学習側（biped_ppo_walk_env.py の _log_watchlist）がログする Watchlist キー
KEY_DISPLACEMENT = "0_Watchlist/episode_displacement_x"
KEY_EP_LENGTH = "0_Watchlist/episode_length_steps"
KEY_BAD_POSE = "0_Watchlist/bad_pose"
KEY_TIME_OUT = "0_Watchlist/time_out"
KEY_REWARD_TOTAL = "0_Watchlist/episode_reward_total"

# 指標の見方（Workspace の Markdown パネルと Report の解説で共用する）
GUIDE_MARKDOWN = """## 0_Watchlist の見方

| 指標 | 好ましい推移 | 悪いサイン |
|------|--------------|------------|
| episode_displacement_x | 右上がり（目安 4 m+） | 0 付近で停滞・負値 |
| episode_length_steps | 長くなる（上限 = 30 s / 0.02 s = 1500） | 短いまま（早期転倒） |
| bad_pose | 下がる | 1.0 付近に張り付き |
| time_out | 学習後半で増える | ずっと 0（全 env 早期終了） |
| episode_reward_total | displacement と同調して上昇 | 報酬だけ上昇 → 報酬ハック疑い |

**判断のコツ**: 報酬が伸びても displacement が伸びない場合は報酬ハックを疑う。
最終判定は学習曲線ではなく `eval_biped_walk.py` で行う。
"""


def build_watchlist_panels() -> list:
    """Watchlist セクションに並べるチャートパネル一覧を作る（Workspace / Report 共用）。"""
    return [
        wr.LinePlot(
            x="Step",
            y=[KEY_DISPLACEMENT],
            title="前進距離 (+X) — 右上がりが好ましい",
            smoothing_factor=0.6,
        ),
        wr.LinePlot(
            x="Step",
            y=[KEY_EP_LENGTH],
            title="エピソード長 — 長くなるのが好ましい（上限 1500）",
            smoothing_factor=0.6,
        ),
        wr.LinePlot(
            x="Step",
            y=[KEY_BAD_POSE, KEY_TIME_OUT],
            title="終了理由 — bad_pose 減 / time_out 増が好ましい",
            smoothing_factor=0.6,
        ),
        wr.LinePlot(
            x="Step",
            y=[KEY_REWARD_TOTAL],
            title="報酬合計 — displacement と同調して上昇が健全",
            smoothing_factor=0.6,
        ),
    ]


def create_workspace(entity: str, project: str) -> str:
    """Watchlist を最上部に置いた Workspace（Saved View）を作成し URL を返す。"""
    workspace = ws.Workspace(
        name="Watchlist Dashboard",
        entity=entity,
        project=project,
        sections=[
            # 監視の本丸。セクションを開いた状態で保存する
            ws.Section(
                name="0_Watchlist（重要指標）",
                panels=[
                    # 目安の説明を隣に常駐させる（グラフと同じセクション内）
                    wr.MarkdownPanel(markdown=GUIDE_MARKDOWN),
                    *build_watchlist_panels(),
                ],
                is_open=True,
            ),
            # 学習健全性（PPO 側）。異常時だけ開けばよいので閉じた状態で保存
            ws.Section(
                name="学習健全性（PPO）",
                panels=[
                    wr.LinePlot(x="Step", y=["Loss/value_function"], title="Value loss — 発散/NaN は異常"),
                    wr.LinePlot(x="Step", y=["Loss/surrogate"], title="Surrogate loss — 小幅な振動が正常"),
                    wr.LinePlot(x="Step", y=["Policy/mean_noise_std"], title="Action std — 急に 0 は探索消滅"),
                    wr.LinePlot(x="Step", y=["Loss/learning_rate"], title="Learning rate（adaptive）"),
                ],
                is_open=False,
            ),
        ],
    )
    saved = workspace.save()
    return saved.url


def create_report(entity: str, project: str) -> str:
    """指標の見方を解説した Report（監視ガイド）を作成し URL を返す。"""
    report = wr.Report(
        entity=entity,
        project=project,
        title="biped_ppo_walk 監視ガイド",
        description="本番学習で見るべき指標と、好ましい/好ましくない推移の判断基準。",
    )
    report.blocks = [
        wr.TableOfContents(),
        wr.H1(text="歩行の出来（最優先）"),
        wr.MarkdownBlock(text=GUIDE_MARKDOWN),
        wr.PanelGrid(
            runsets=[wr.Runset(entity=entity, project=project)],
            panels=build_watchlist_panels(),
        ),
        wr.H1(text="学習健全性（PPO）"),
        wr.MarkdownBlock(
            text=(
                "アルゴリズム側の診断指標。歩行の出来ではなく「学習が壊れていないか」を見る。\n\n"
                "- **Action std**: 序盤はある程度あり、ゆっくり下がるのが正常。急に 0 付近 → 探索消滅。\n"
                "- **Value loss / Surrogate loss**: 小幅な振動は正常。爆発・NaN は学習崩壊なので即停止。\n"
                "- **Learning rate**: adaptive スケジュールが desired_kl=0.02 付近に収まるよう自動調整する。\n"
                "  極端な値に張り付き続ける場合は報酬スケールや学習率設定を疑う。"
            )
        ),
        wr.PanelGrid(
            runsets=[wr.Runset(entity=entity, project=project)],
            panels=[
                wr.LinePlot(x="Step", y=["Policy/mean_noise_std"], title="Action std"),
                wr.LinePlot(x="Step", y=["Loss/value_function"], title="Value loss"),
                wr.LinePlot(x="Step", y=["Loss/surrogate"], title="Surrogate loss"),
                wr.LinePlot(x="Step", y=["Loss/learning_rate"], title="Learning rate"),
            ],
        ),
        wr.H1(text="運用メモ"),
        wr.MarkdownBlock(
            text=(
                "- 学習は headless で回し、可視確認は `play.py`、採点は `eval_biped_walk.py`（学習と可視化の分離）。\n"
                "- 学習曲線だけで成功と判断しない（1 run = 1 仮説、採点は eval）。\n"
                "- Watchlist の指標は `biped_ppo_walk_env.py` の `_log_watchlist()` がログしている。\n"
                "  キーを増やす場合は 3〜5 個に絞る（増やしすぎると Watchlist の意味がなくなる）。"
            )
        ),
    ]
    saved = report.save()
    return saved.url


def main() -> None:
    parser = argparse.ArgumentParser(description="Create WandB workspace/report for biped_ppo_walk.")
    parser.add_argument("--entity", type=str, default="yuukilab-channel", help="WandB entity (team/user).")
    parser.add_argument("--project", type=str, default="biped_ppo_walk", help="WandB project name.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--workspace-only", action="store_true", help="Workspace（監視ビュー）のみ作成する。")
    group.add_argument("--report-only", action="store_true", help="Report（監視ガイド）のみ作成する。")
    args = parser.parse_args()

    if not args.report_only:
        url = create_workspace(args.entity, args.project)
        print(f"[OK] Workspace created: {url}")

    if not args.workspace_only:
        url = create_report(args.entity, args.project)
        print(f"[OK] Report created: {url}")


if __name__ == "__main__":
    main()
