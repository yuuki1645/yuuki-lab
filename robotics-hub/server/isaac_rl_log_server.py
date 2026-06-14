#!/usr/bin/env python3
# type: ignore
"""Isaac Lab (RSL-RL) の TensorBoard ログを Robotics Hub 向け JSON API で提供する。

``events.out.tfevents.*`` を読み取り、学習進捗グラフ用の scalar 系列を返す。
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from flask import Flask, jsonify, request
from flask_cors import CORS
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

LOG = logging.getLogger("isaac_rl_log_server")

# Hub 画面で優先表示する scalar（順序維持）
DEFAULT_SCALAR_TAGS: tuple[str, ...] = (
    "Train/mean_reward",
    "Train/mean_episode_length",
    "Reward/mean_forward",
    "Reward/mean_effort",
    "Policy/mean_noise_std",
    "Loss/surrogate",
    "Loss/value_function",
    "Loss/entropy",
    "Loss/learning_rate",
    "Perf/total_fps",
    "Perf/collection time",
    "Perf/learning_time",
)

_TFEvents_RE = re.compile(r"^events\.out\.tfevents\.")

# test-isaac-project の train.py が書き込む logs/rsl_rl（環境変数未設定時の既定）
# 例: C:\Users\yuukilab\test-isaac-project\TestIsaacProject\logs\rsl_rl
def _standard_log_root_candidates() -> list[Path]:
    robotics_hub = Path(__file__).resolve().parent.parent
    yuuki_lab = robotics_hub.parent
    home = Path.home()
    return [
        home / "test-isaac-project" / "TestIsaacProject" / "logs" / "rsl_rl",
        yuuki_lab.parent / "test-isaac-project" / "TestIsaacProject" / "logs" / "rsl_rl",
        yuuki_lab / "test-isaac-project" / "TestIsaacProject" / "logs" / "rsl_rl",
        Path.cwd() / "logs" / "rsl_rl",
    ]


def _default_log_root() -> Path:
    """環境変数 ``ISAAC_RL_LOG_ROOT`` または test-isaac-project の logs/rsl_rl を推定。"""
    env = os.environ.get("ISAAC_RL_LOG_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()

    for candidate in _standard_log_root_candidates():
        if candidate.is_dir():
            return candidate.resolve()
    # 存在しなくても home 配下の典型パスを返す（起動時に warning）
    return _standard_log_root_candidates()[0].resolve()


def _find_tfevents_file(run_dir: Path) -> Path | None:
    """run ディレクトリ直下の TensorBoard event ファイルを返す。"""
    if not run_dir.is_dir():
        return None
    candidates = sorted(
        (p for p in run_dir.iterdir() if p.is_file() and _TFEvents_RE.match(p.name)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_event_accumulator(run_dir: Path) -> EventAccumulator | None:
    """TensorBoard event を読み込む。学習中は追記されるため毎回 Reload する。"""
    events_path = _find_tfevents_file(run_dir)
    if events_path is None:
        return None
    # size_guidance=0 で全 scalar を保持（run あたり数千点程度）
    ea = EventAccumulator(str(run_dir), size_guidance={"scalars": 0})
    ea.Reload()
    return ea


def _scalar_points(ea: EventAccumulator, tag: str) -> list[dict[str, float]]:
    """1 つの scalar 系列を JSON 化可能な dict リストに変換。"""
    try:
        events = ea.Scalars(tag)
    except KeyError:
        return []
    return [{"step": float(ev.step), "value": float(ev.value), "wall_time": float(ev.wall_time)} for ev in events]


def _latest_from_points(points: list[dict[str, float]]) -> dict[str, float] | None:
    if not points:
        return None
    last = points[-1]
    return {"step": last["step"], "value": last["value"]}


def _run_mtime(run_dir: Path) -> float:
    events = _find_tfevents_file(run_dir)
    if events is not None:
        return events.stat().st_mtime
    return run_dir.stat().st_mtime


def _list_checkpoints(run_dir: Path) -> list[str]:
    return sorted(p.name for p in run_dir.glob("model_*.pt"))


def _read_yaml_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else None


def _is_tailscale_ipv4(ip: str) -> bool:
    """Tailscale の CGNAT レンジ 100.64.0.0/10 かどうか。"""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        first, second = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    return first == 100 and 64 <= second <= 127


def _tailscale_ipv4() -> str | None:
    """``tailscale ip -4`` が使えれば Tailscale IPv4 を返す。"""
    try:
        proc = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        line = proc.stdout.strip().splitlines()[0].strip() if proc.stdout.strip() else ""
        if line and _is_tailscale_ipv4(line):
            return line
    except (FileNotFoundError, subprocess.TimeoutExpired, IndexError, OSError):
        pass
    return None


def _lan_ipv4_addresses() -> list[str]:
    """Tailscale 以外の LAN IPv4（重複除去）。"""
    seen: set[str] = set()
    result: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127.") or ip in seen or _is_tailscale_ipv4(ip):
                continue
            seen.add(ip)
            result.append(ip)
    except OSError:
        pass
    return result


def _collect_access_urls(port: int) -> dict[str, Any]:
    """Hub / スマホ向けにアクセス URL 一覧を組み立てる。"""
    ts_ip = _tailscale_ipv4()
    lan = _lan_ipv4_addresses()
    return {
        "port": port,
        "localhost": f"http://127.0.0.1:{port}",
        "lan": [f"http://{ip}:{port}" for ip in lan],
        "tailscale": f"http://{ts_ip}:{port}" if ts_ip else None,
        "tailscale_ip": ts_ip,
    }


def _log_access_urls(host: str, port: int) -> None:
    urls = _collect_access_urls(port)
    LOG.info("Listening on %s:%s", host, port)
    LOG.info("  localhost: %s", urls["localhost"])
    for lan_url in urls["lan"]:
        LOG.info("  LAN: %s", lan_url)
    if urls["tailscale"]:
        LOG.info("  Tailscale (外出先スマホ向け): %s", urls["tailscale"])
    else:
        LOG.info("  Tailscale: (未検出 — tailscale ip -4 で IP を確認してください)")


def create_app(log_root: Path, port: int = 8792) -> Flask:
    app = Flask(__name__)
    CORS(app)

    @app.route("/api/health")
    def health() -> Any:
        return jsonify(
            {
                "status": "ok",
                "log_root": str(log_root),
                "log_root_exists": log_root.is_dir(),
                "access_urls": _collect_access_urls(port),
            }
        )

    @app.route("/api/config")
    def config() -> Any:
        return jsonify({"log_root": str(log_root), "access_urls": _collect_access_urls(port)})

    @app.route("/api/experiments")
    def experiments() -> Any:
        if not log_root.is_dir():
            return jsonify({"experiments": [], "log_root": str(log_root)})
        names = sorted(p.name for p in log_root.iterdir() if p.is_dir())
        return jsonify({"experiments": names, "log_root": str(log_root)})

    @app.route("/api/experiments/<experiment>/runs")
    def list_runs(experiment: str) -> Any:
        exp_dir = log_root / experiment
        if not exp_dir.is_dir():
            return jsonify({"error": f"experiment not found: {experiment}"}), 404
        runs: list[dict[str, Any]] = []
        for run_dir in sorted(exp_dir.iterdir(), key=lambda p: _run_mtime(p), reverse=True):
            if not run_dir.is_dir():
                continue
            ea = _load_event_accumulator(run_dir)
            latest_iter: float | None = None
            if ea is not None and ea.Tags().get("scalars"):
                # Train/mean_reward があればそれを基準に最新 iter を取る
                ref_tag = "Train/mean_reward"
                tags = ea.Tags()["scalars"]
                if ref_tag in tags:
                    pts = ea.Scalars(ref_tag)
                    if pts:
                        latest_iter = float(pts[-1].step)
                elif tags:
                    pts = ea.Scalars(tags[0])
                    if pts:
                        latest_iter = float(pts[-1].step)
            runs.append(
                {
                    "id": run_dir.name,
                    "mtime": _run_mtime(run_dir),
                    "mtime_iso": datetime.fromtimestamp(_run_mtime(run_dir), tz=timezone.utc).isoformat(),
                    "latest_iteration": latest_iter,
                    "has_events": _find_tfevents_file(run_dir) is not None,
                    "checkpoints": _list_checkpoints(run_dir),
                }
            )
        return jsonify({"experiment": experiment, "runs": runs})

    @app.route("/api/experiments/<experiment>/runs/<run_id>/meta")
    def run_meta(experiment: str, run_id: str) -> Any:
        run_dir = log_root / experiment / run_id
        if not run_dir.is_dir():
            return jsonify({"error": "run not found"}), 404
        agent = _read_yaml_if_exists(run_dir / "params" / "agent.yaml")
        env_cfg = _read_yaml_if_exists(run_dir / "params" / "env.yaml")
        return jsonify(
            {
                "experiment": experiment,
                "run_id": run_id,
                "agent": agent,
                "env": env_cfg,
                "checkpoints": _list_checkpoints(run_dir),
                "events_file": _find_tfevents_file(run_dir).name if _find_tfevents_file(run_dir) else None,
            }
        )

    @app.route("/api/experiments/<experiment>/runs/<run_id>/scalars")
    def run_scalars(experiment: str, run_id: str) -> Any:
        run_dir = log_root / experiment / run_id
        if not run_dir.is_dir():
            return jsonify({"error": "run not found"}), 404
        ea = _load_event_accumulator(run_dir)
        if ea is None:
            return jsonify({"error": "no tensorboard events in run"}), 404

        tags_param = request.args.get("tags", "")
        if tags_param.strip():
            tags = [t.strip() for t in tags_param.split(",") if t.strip()]
        else:
            available = set(ea.Tags().get("scalars", []))
            tags = [t for t in DEFAULT_SCALAR_TAGS if t in available]
            # 既定リストに無いカスタム tag も末尾に追加
            for t in sorted(available):
                if t not in tags:
                    tags.append(t)

        series: dict[str, list[dict[str, float]]] = {}
        latest: dict[str, dict[str, float]] = {}
        for tag in tags:
            pts = _scalar_points(ea, tag)
            if pts:
                series[tag] = pts
                last = _latest_from_points(pts)
                if last is not None:
                    latest[tag] = last

        latest_iter = None
        if "Train/mean_reward" in latest:
            latest_iter = latest["Train/mean_reward"]["step"]
        elif latest:
            latest_iter = next(iter(latest.values()))["step"]

        events_file = _find_tfevents_file(run_dir)
        return jsonify(
            {
                "experiment": experiment,
                "run_id": run_id,
                "latest_iteration": latest_iter,
                "events_mtime": events_file.stat().st_mtime if events_file else None,
                "events_mtime_iso": datetime.fromtimestamp(events_file.stat().st_mtime, tz=timezone.utc).isoformat()
                if events_file
                else None,
                "series": series,
                "latest": latest,
            }
        )

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Isaac Lab RL log API for Robotics Hub")
    parser.add_argument("--host", default=os.environ.get("ISAAC_RL_LOG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ISAAC_RL_LOG_PORT", "8792")))
    parser.add_argument("--log-root", default=str(_default_log_root()), help="logs/rsl_rl のルート")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    log_root = Path(args.log_root).expanduser().resolve()
    LOG.info("log_root=%s", log_root)
    if not log_root.is_dir():
        LOG.warning("log_root does not exist yet: %s", log_root)

    _log_access_urls(args.host, args.port)
    app = create_app(log_root, port=args.port)
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
