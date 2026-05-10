# type: ignore

from __future__ import annotations

import logging
import math
from typing import Any

from flask import Flask, current_app, jsonify, request
from flask_cors import CORS

from mujoco_sim.core import Simulation
LOG = logging.getLogger("mujoco_sim.api")

CTRL_MODES = ("rad", "deg")


def _get_sim() -> Simulation:
    return current_app.extensions["simulation"]


def _normalize_ctrl(body: dict) -> dict[str, float] | None:
    """ボディの ctrl を MuJoCo の単位（rad）に正規化して返す。

    - ``mode`` 省略時は ``"rad"``（後方互換）。
    - ``mode == "deg"`` のときは各値を度→ラジアンに換算する。
    - ``ctrl`` 自体が無いときは ``None`` を返す。
    - 入力が壊れているときは ``TypeError`` または ``ValueError`` を送出する。
    """

    ctrl = body.get("ctrl")
    if ctrl is None:
        return None
    if not isinstance(ctrl, dict):
        raise TypeError("ctrl must be an object mapping names to numbers")

    mode = body.get("mode", "rad")
    if mode not in CTRL_MODES:
        raise ValueError(
            f"mode must be one of {CTRL_MODES} (got {mode!r})"
        )

    if mode == "deg":
        return {str(k): math.radians(float(v)) for k, v in ctrl.items()}
    return {str(k): float(v) for k, v in ctrl.items()}


def create_app(simulation: Simulation | None = None) -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.extensions["simulation"] = simulation or Simulation()

    @app.before_request
    def _log_request() -> None:
        path = request.path
        if path != "/health" and not path.startswith("/api"):
            return
        client = request.remote_addr or "?"
        detail = ""
        if request.method in ("POST", "PUT") and path in ("/api/step", "/api/ctrl"):
            payload = request.get_json(silent=True)
            if isinstance(payload, dict):
                detail = f" json={payload!r}"
        LOG.info("%s %s client=%s%s", request.method, path, client, detail)

    @app.route("/health", methods=["GET"])
    def health() -> Any:
        return jsonify({"status": "ok"})

    @app.route("/api/meta", methods=["GET"])
    def meta() -> Any:
        sim = _get_sim()
        return jsonify(
            {
                "xml_path": str(sim.xml_path),
                "actuator_names": sim.actuator_names(),
            }
        )

    @app.route("/api/state", methods=["GET"])
    def get_state() -> Any:
        return jsonify(_get_sim().state_dict())

    @app.route("/api/reset", methods=["POST"])
    def post_reset() -> Any:
        sim = _get_sim()
        sim.reset()
        return jsonify(sim.state_dict())

    @app.route("/api/step", methods=["POST"])
    def post_step() -> Any:
        body = request.get_json(silent=True)
        if body is None:
            body = {}
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object expected"}), 400

        n_raw = body.get("n", 1)
        try:
            n = int(n_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "n must be an integer"}), 400
        if n < 1 or n > 10_000:
            return jsonify({"error": "n must be between 1 and 10000"}), 400

        sim = _get_sim()
        try:
            ctrl_rad = _normalize_ctrl(body)
            if ctrl_rad:
                sim.set_ctrl(ctrl_rad)
            sim.step(n)
        except (KeyError, TypeError, ValueError) as e:
            LOG.warning("POST /api/step rejected: %s", e)
            return jsonify({"error": str(e)}), 400
        return jsonify(sim.state_dict())

    @app.route("/api/ctrl", methods=["PUT"])
    def put_ctrl() -> Any:
        body = request.get_json(silent=True)
        if body is None or not isinstance(body, dict):
            return jsonify({"error": "JSON object expected"}), 400
        if body.get("ctrl") is None:
            return jsonify({"error": "ctrl object required"}), 400

        sim = _get_sim()
        try:
            ctrl_rad = _normalize_ctrl(body)
            if ctrl_rad is None:
                return jsonify({"error": "ctrl object required"}), 400
            sim.set_ctrl(ctrl_rad)
        except (KeyError, TypeError, ValueError) as e:
            LOG.warning("PUT /api/ctrl rejected: %s", e)
            return jsonify({"error": str(e)}), 400
        return jsonify(sim.state_dict())

    return app
