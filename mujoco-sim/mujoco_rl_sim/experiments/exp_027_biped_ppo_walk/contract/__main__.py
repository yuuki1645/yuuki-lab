"""python -m contract — 契約の検証・ドキュメント生成。"""

from __future__ import annotations

import argparse
import sys

from contract.codegen import observation_markdown_table, reward_log_markdown_list
from experiment_contract import TELEMETRY_CONTRACT


def main(argv: list[str] | None = None) -> int:
  p = argparse.ArgumentParser(description="exp_027 契約ユーティリティ")
  sub = p.add_subparsers(dest="cmd", required=True)

  sub.add_parser("validate", help="biped_walk_v1 レイアウトの自己検証")

  md_p = sub.add_parser("markdown", help="観測・報酬ログの Markdown を stdout に出力")
  md_p.add_argument(
    "--reward",
    action="store_true",
    help="報酬ログキー一覧も出力",
  )

  args = p.parse_args(argv)
  contract = TELEMETRY_CONTRACT

  if args.cmd == "validate":
    contract.validate()
    print(f"OK: {contract.schema_id} obs_dim={contract.observation.obs_dim}")
    return 0

  if args.cmd == "markdown":
    print(f"<!-- schema: {contract.schema_id} -->\n")
    print(observation_markdown_table(contract))
    if args.reward:
      print("\n### 報酬ログキー（契約）\n")
      print(reward_log_markdown_list(contract))
    return 0

  return 1


if __name__ == "__main__":
  raise SystemExit(main())
