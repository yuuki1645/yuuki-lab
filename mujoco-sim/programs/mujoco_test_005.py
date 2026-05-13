# type: ignore

"""
オフスクリーン描画（mujoco.Renderer）でシミュをレンダリングし、MP4 に保存する。

CSV は Robotics Hub データビュワー用 ``imu.csv`` と同じ列名（+ 末尾にシム用メタ列）で出力する。

依存: ``pip install -e ".[video]"`` または ``pip install imageio imageio-ffmpeg``

例::

  cd mujoco-sim/programs
  python mujoco_test_005.py --steps 3000 --subsample 8 --out run.mp4 --write-manifest
  # run.csv と manifest.json（Hub 用 acquisition=mujoco）を同ディレクトリに出力
"""

from __future__ import annotations

import argparse
import csv
import json
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

# データビュワー用 wall_unix の単調性（実機と重ならないよう大きめの基準時刻 + 再生オフセット）
_HUB_WALL_UNIX_BASE = 1_700_000_000.0


def _sensor_vec(model: mujoco.MjModel, data: mujoco.MjData, name: str, dim: int) -> tuple[float, ...]:
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, name)
    if sid < 0:
        raise SystemExit(
            f"センサー {name!r} が見つかりません（MJCF に定義があるか、--acc-sensor / --gyro-sensor を確認）"
        )
    adr = int(model.sensor_adr[sid])
    return tuple(float(data.sensordata[adr + k]) for k in range(dim))


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
    p.add_argument(
        "--acc-sensor",
        type=str,
        default="imu_acc",
        help="加速度センサ名（MJCF の <accelerometer name=...>）",
    )
    p.add_argument(
        "--gyro-sensor",
        type=str,
        default="imu_gyro",
        help="ジャイロセンサ名（MJCF の <gyro name=...>）",
    )
    p.add_argument(
        "--csv",
        type=str,
        default=None,
        help="センサー CSV（省略時は --out と同名の .csv）。Hub 用 imu.csv にコピー可",
    )
    p.add_argument(
        "--write-manifest",
        nargs="?",
        const="",
        default=None,
        help="manifest.json を出力。引数省略時は --out と同じディレクトリの manifest.json",
    )
    return p.parse_args()


def _write_manifest_json(
    path: Path,
    *,
    xml_path: str,
    out_fps: float,
    subsample: int,
    timestep: float,
    video_file: str = "video.mp4",
) -> None:
    payload = {
        "acquisition": "mujoco",
        "schema_version": 1,
        "perf_timestamp_at_video_zero": 0.0,
        "video_file": video_file,
        "acquisition_detail": {
            "mjcf": xml_path,
            "video_fps": out_fps,
            "subsample": subsample,
            "timestep": timestep,
            "imu_accel_unit": "m/s2",
            "imu_gyro_unit": "rad/s",
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    args = _parse_args()
    xml_path = str(Path(args.xml).resolve())
    model = mujoco.MjModel.from_xml_path(xml_path)
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

    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.is_absolute():
            csv_path = Path.cwd() / csv_path
    else:
        csv_path = out_path.with_suffix(".csv")

    acc_name = str(args.acc_sensor)
    gyro_name = str(args.gyro_sensor)

    hub_header = [
        "wall_unix",
        "perf_timestamp",
        "mock",
        "accel_x",
        "accel_y",
        "accel_z",
        "gyro_x",
        "gyro_y",
        "gyro_z",
        "sim_time_s",
        "frame_index",
        "mj_step",
    ]

    n_frames = 0
    with open(csv_path, "w", newline="", encoding="utf-8") as csv_f:
        csv_w = csv.writer(csv_f)
        csv_w.writerow(hub_header)
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
                perf_ts = n_frames / out_fps
                wall = _HUB_WALL_UNIX_BASE + perf_ts
                acc = _sensor_vec(model, data, acc_name, 3)
                gyro = _sensor_vec(model, data, gyro_name, 3)
                sim_t = float(data.time)
                csv_w.writerow(
                    [
                        wall,
                        perf_ts,
                        "True",
                        acc[0],
                        acc[1],
                        acc[2],
                        gyro[0],
                        gyro[1],
                        gyro[2],
                        sim_t,
                        n_frames,
                        i + 1,
                    ]
                )
                if cam_id >= 0:
                    renderer.update_scene(data, camera=cam_id)
                else:
                    renderer.update_scene(data)
                rgb = renderer.render()
                writer.append_data(rgb)
                n_frames += 1

    if args.write_manifest is not None:
        if args.write_manifest == "":
            manifest_path = out_path.parent / "manifest.json"
        else:
            manifest_path = Path(args.write_manifest)
            if not manifest_path.is_absolute():
                manifest_path = Path.cwd() / manifest_path
        _write_manifest_json(
            manifest_path,
            xml_path=xml_path,
            out_fps=out_fps,
            subsample=subsample,
            timestep=dt,
            video_file="video.mp4",
        )
        print(f"wrote {manifest_path} (acquisition=mujoco, video_file=video.mp4)")

    print(
        f"wrote {out_path} ({n_frames} frames, ~{n_frames / out_fps:.2f}s playback, "
        f"fps={out_fps:.2f}, subsample={subsample}, sim_time~{args.steps * dt:.3f}s)"
    )
    print(
        f"wrote {csv_path} ({n_frames} rows, Hub-compatible imu columns; "
        f"sensors {acc_name!r} / {gyro_name!r})"
    )


if __name__ == "__main__":
    main()
