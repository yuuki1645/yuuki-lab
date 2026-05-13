# type: ignore
"""MuJoCo passive viewer + Robotics Hub「ビュワー補助」用 HTTP ブリッジ。

別スレッドで Flask（既定 **8788**）を立て、Hub からシミュ状態の取得・再生制御・
表示オプション変更ができる。メインスレッドは ``launch_passive`` のループ。

例::

  cd mujoco-sim/programs
  python mujoco_test_009.py
  python mujoco_test_009.py --xml ../mujoco_sim_assets/xmls/004_leg_1joint/main.xml --port 8788

Hub 側は「MuJoCo ビュワー補助」ページを開き、接続先 URL が本プロセスの
``http://<ホスト>:<port>`` と一致するようにする（既定は同一 LAN の :8788）。
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

_SIM_ROOT = Path(__file__).resolve().parents[1]
if str(_SIM_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIM_ROOT))

import mujoco  # noqa: E402
import mujoco.viewer  # noqa: E402

from mujoco_sim_common.viewer_aux_bridge import (  # noqa: E402
    ViewerAuxRuntime,
    start_viewer_aux_http,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--xml",
        type=str,
        default=str(_SIM_ROOT / "mujoco_sim_assets/xmls/004_leg_1joint/main.xml"),
        help="読み込む MJCF（main.xml）",
    )
    p.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="ビュワー補助 API の bind アドレス",
    )
    p.add_argument(
        "--port",
        type=int,
        default=8788,
        help="ビュワー補助 API のポート（Hub の VITE_MUJOCO_VIEWER_AUX_URL と揃える）",
    )
    p.add_argument(
        "--no-http",
        action="store_true",
        help="Flask を起動せず viewer のみ（デバッグ用）",
    )
    p.add_argument(
        "--quiet-http",
        action="store_true",
        help="Werkzeug のアクセスログを抑える",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    xml_path = Path(args.xml).expanduser().resolve()
    if not xml_path.is_file():
        raise SystemExit(f"[009] MJCF が見つかりません: {xml_path}")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    model = mujoco.MjModel.from_xml_path(str(xml_path))
    data = mujoco.MjData(model)
    runtime = ViewerAuxRuntime(
        model=model,
        data=data,
        xml_path=str(xml_path),
    )

    if not args.no_http:
        start_viewer_aux_http(
            runtime,
            host=args.host,
            port=int(args.port),
            quiet=bool(args.quiet_http),
        )
        logging.getLogger("mujoco_test_009").info(
            "Hub 用ビュワー補助 API: http://%s:%s （/health, /api/viewer/*）",
            args.host,
            args.port,
        )

    logging.getLogger("mujoco_test_009").info(
        "パッシブ viewer を開きました。ウィンドウを閉じると終了します。"
    )

    with mujoco.viewer.launch_passive(model, data) as viewer:
        runtime.attach_viewer_handle(viewer)
        while viewer.is_running():
            if runtime.paused:
                runtime.main_tick_paused_sync_only(viewer)
            else:
                runtime.main_tick(viewer)
            runtime.sleep_after_tick()


if __name__ == "__main__":
    main()
