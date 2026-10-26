#!/usr/bin/env python3
"""
USB を開く総合デバッグ。入口の正本は link/host/lab_debug.py で、このファイルを起動する。

  pip install -r tools/requirements.txt
  python tools/lab_debug.py

CoreS3（USB ver 15）と、机上の rt-usb（ver 14）のどちらも、このプロセスが COM を開く。
Tk GUI は非推奨。操作は robotics-hub の
「実機テレメトリ（M5）」http://127.0.0.1:5173/m5-telemetry。
USB 中継のため本プロセスは起動したままにする（機能は残している）。

iPad（robotics-hub の「実機テレメトリ（M5）」）へは、このプロセスが
Socket.IO :8794 で中継する。iPad 接続中は PC 側のロボット操作は表示のみ
（全停止と USB 接続／切断は残す）。

依存マップ（tools/ は起動物、tools/lib/ は部品）:
  このファイル              Tk を起動する。外からは link/host/lab_debug.py が呼ぶ
  lib/lab_app.py            Tk GUI（LabApp）。操作は apply_op()
  lib/lab_usb.py            AtomWorker / AtomSession / COM / 起動音
  lib/lab_model.py          Frame / JointRoute / 変換
  lib/lab_const.py          色・軸数・WAV・閾値
  lib/lab_plot.py           折れ線
  lib/lab_pc_cal.py         PC 掃引校正
  lib/rt_usb_proto.py       USB フレーム（ファーム usb_proto.hpp と揃える）
  lib/cal_map_io.py         校正マップ JSON
  lib/m5_hub_bridge.py      Hub / iPad 中継 :8794
  lib/m5_record_store.py    本記録
  lib/cop_ankle_ctrl.py     かかとピッチ COP
  lib/df9_force.py          足裏 DF9-40 の電圧→力
他の起動物: rt_monitor.py（1台グラフ）、rt_usb_log.py（CLI ログ）
"""

from __future__ import annotations

import sys
from pathlib import Path

# tools/ を import パスへ。lib/ を `import lib.xxx` で読むため。
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from lib.lab_app import LabApp


def main() -> None:
    app = LabApp()
    app.mainloop()


if __name__ == "__main__":
    main()
