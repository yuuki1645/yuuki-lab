# type: ignore

"""
オフスクリーン描画（mujoco.Renderer）でシミュをレンダリングし、MP4 に保存する。

依存: ``pip install -e ".[video]"`` または ``pip install imageio imageio-ffmpeg``

例::

  cd mujoco-sim/programs
  python mujoco_test_005.py --steps 3000 --subsample 8 --out run.mp4
"""

import argparse
import sys
from pathlib import Path

_SIM_ROOT = Path(__file__).resolve().parents[1]
if str(_SIM_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIM_ROOT))

import mujoco  # noqa: E402

try:
    import imageio.v2 as imageio  # noqa: E402
except ImportError as e:
    raise SystemExit(
        "imageio が必要です。例: pip install imageio imageio-ffmpeg\n"
        "または mujoco-sim ルートで: pip install -e \".[video]\""
    ) from e


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--xml",
        type=str,
        default=str(_SIM_ROOT / "mujoco_sim_assets/xmls/004_leg_1joint/main.xml"),
        help="MJCF パス",
    )
    p.add_argument("--out", type=str, default="mujoco_test_005_out.mp4", help="出力 MP4")
    p.add_argument("--steps", type=int, default=2500, help="mj_step 回数")
    p.add_argument(
        "--subsample",
        type=int,
        default=0,
        help="N ステップに 1 回だけフレームを取る（1=毎ステップ）。0 のとき --fps から自動",
    )
    p.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="動画のフレームレート。--subsample が 0 のとき、dt から取り込み間引きを推定",
    )
    p.add_argument("--width", type=int, default=1280, help="レンダー幅")
    p.add_argument("--height", type=int, default=720, help="レンダー高さ")
    p.add_argument(
        "--camera",
        type=int,
        default=-1,
        help="MJCF 内カメラ id（0 始まり）。-1 でシーン既定カメラ",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    model = mujoco.MjModel.from_xml_path(args.xml)
    data = mujoco.MjData(model)
    gw, gh = int(model.vis.global_.offwidth), int(model.vis.global_.offheight)
    if args.width > gw or args.height > gh:
        model.vis.global_.offwidth = max(gw, args.width)
        model.vis.global_.offheight = max(gh, args.height)
    dt = float(model.opt.timestep)
    subsample = int(args.subsample)
    if subsample <= 0:
        subsample = max(1, int(round(1.0 / (dt * float(args.fps)))))
    out_fps = 1.0 / (dt * float(subsample))

    renderer = mujoco.Renderer(model, height=args.height, width=args.width)
    cam_id = int(args.camera)

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path

    n_frames = 0
    with imageio.get_writer(
        str(out_path),
        fps=out_fps,
        codec="libx264",
        quality=8,
        macro_block_size=1,
    ) as writer:
        for i in range(int(args.steps)):
            mujoco.mj_step(model, data)
            if (i + 1) % subsample != 0:
                continue
            if cam_id >= 0:
                renderer.update_scene(data, camera=cam_id)
            else:
                renderer.update_scene(data)
            rgb = renderer.render()
            writer.append_data(rgb)
            n_frames += 1

    print(
        f"wrote {out_path} ({n_frames} frames, ~{n_frames / out_fps:.2f}s playback, "
        f"fps={out_fps:.2f}, subsample={subsample}, sim_time~{args.steps * dt:.3f}s)"
    )


if __name__ == "__main__":
    main()
