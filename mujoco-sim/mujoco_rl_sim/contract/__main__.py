"""python -m mujoco_rl_sim.contract — 契約の検証・ドキュメント生成。"""

from __future__ import annotations

import argparse
import sys

from mujoco_rl_sim.contract.biped_v1 import BIPED_PPO_V1
from mujoco_rl_sim.contract.codegen import observation_markdown_table, reward_log_markdown_list


def main(argv: list[str] | None = None) -> int:
  p = argparse.ArgumentParser(description="mujoco_rl_sim 契約ユーティリティ")
  sub = p.add_subparsers(dest="cmd", required=True)

  sub.add_parser("validate", help="biped_ppo_v1 レイアウトの自己検証")

  md_p = sub.add_parser("markdown", help="観測・報酬ログの Markdown を stdout に出力")
  md_p.add_argument(
    "--reward",
    action="store_true",
    help="報酬ログキー一覧も出力",
  )

  args = p.parse_args(argv)

  if args.cmd == "validate":
    BIPED_PPO_V1.validate()
    print(f"OK: {BIPED_PPO_V1.schema_id} obs_dim={BIPED_PPO_V1.observation.obs_dim}")
    return 0

  if args.cmd == "markdown":
    print(f"<!-- schema: {BIPED_PPO_V1.schema_id} -->\n")
    print(observation_markdown_table(BIPED_PPO_V1))
    if args.reward:
      print("\n### 報酬ログキー（契約）\n")
      print(reward_log_markdown_list(BIPED_PPO_V1))
    return 0

  return 1


if __name__ == "__main__":
  raise SystemExit(main())
