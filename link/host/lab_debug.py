#!/usr/bin/env python3
"""
USB-C を握る唯一の入口。ATOM も CoreS3 も、このプロセスが COM を開く。

画面の操作は robotics-hub。ここは中継と、残している Tk を起動するだけ。
Tk に新しい操作は足さない。CoreS3（USB ver 15）の HELLO から切断までは、
このプロセスが実験データを自動で残す。保存先はユーザーの storage.yaml。
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[2] / "atom-rt" / "tools"
sys.path.insert(0, str(_TOOLS))
runpy.run_path(str(_TOOLS / "lab_debug.py"), run_name="__main__")
