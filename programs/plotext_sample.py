"""plotext でターミナルにグラフを描くサンプル。

依存: pip install plotext

実行例:
  python programs/plotext_sample.py
  python programs/plotext_sample.py --demo reward

Windows: 既定の cp932 だと記号出力で UnicodeEncodeError になりやすい。
本スクリプトは stdout を UTF-8 に切り替える。表示が崩れる場合は
``chcp 65001`` 後に実行するか、Windows Terminal を使う。
"""

from __future__ import annotations

import argparse
import random
import sys

import plotext as plt

# Windows (cp932) では plotext の記号出力で UnicodeEncodeError になりやすい
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
  sys.stdout.reconfigure(encoding="utf-8")


def demo_line() -> None:
  """単純な折れ線グラフ。"""
  y = plt.sin(periods=2, length=80)
  plt.plot(y, label="sin")
  plt.title("Line Plot (plotext)")
  plt.xlabel("step")
  plt.ylabel("value")
  plt.show()


def demo_multi() -> None:
  """複数系列と凡例。"""
  y1 = plt.sin(periods=2, length=60)
  y2 = plt.sin(periods=2, length=60, phase=-0.5)
  plt.plot(y1, label="series A")
  plt.scatter(y2, label="series B")
  plt.title("Multiple Data Sets")
  plt.show()


def demo_reward() -> None:
  """RL のエピソード報酬っぽいノイジーな曲線 + 移動平均。"""
  random.seed(0)
  episodes = list(range(1, 101))
  rewards = []
  value = -2.0
  for _ in episodes:
    value += random.gauss(0.08, 0.35)
    rewards.append(value)

  window = 10
  moving_avg = [
    sum(rewards[i - window : i]) / window if i >= window else rewards[i]
    for i in range(1, len(rewards) + 1)
  ]

  plt.plot(episodes, rewards, label="episode reward")
  plt.plot(episodes, moving_avg, label=f"moving avg ({window})")
  plt.title("Episode Reward (sample)")
  plt.xlabel("episode")
  plt.ylabel("reward")
  plt.show()


def demo_bar() -> None:
  """棒グラフの例。"""
  labels = ["alive", "forward", "energy", "action_rate"]
  values = [0.4, 1.2, -0.15, -0.05]
  plt.bar(labels, values)
  plt.title("Reward Components (sample)")
  plt.show()


DEMOS = {
  "line": demo_line,
  "multi": demo_multi,
  "reward": demo_reward,
  "bar": demo_bar,
}


def main() -> None:
  parser = argparse.ArgumentParser(description="plotext terminal plot samples")
  parser.add_argument(
    "--demo",
    choices=sorted(DEMOS),
    default="reward",
    help="which sample to run (default: reward)",
  )
  args = parser.parse_args()
  DEMOS[args.demo]()


if __name__ == "__main__":
  main()
