# type: ignore

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, current_app, jsonify, request
from flask_cors import CORS

from mujoco_sim.core import Simulation
LOG = logging.getLogger("mujoco_sim.api")


def _get_sim() -> Simulation:
    return current_app.extensions["simulation"]


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

        ctrl = body.get("ctrl")
        if ctrl is not None and not isinstance(ctrl, dict):
            return jsonify({"error": "ctrl must be an object mapping names to numbers"}), 400

        sim = _get_sim()
        try:
            if ctrl:
                sim.set_ctrl({str(k): float(v) for k, v in ctrl.items()})
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
        ctrl = body.get("ctrl")
        if ctrl is None or not isinstance(ctrl, dict):
            return jsonify({"error": "ctrl object required"}), 400

        sim = _get_sim()
        try:
            sim.set_ctrl({str(k): float(v) for k, v in ctrl.items()})
        except (KeyError, TypeError, ValueError) as e:
            LOG.warning("PUT /api/ctrl rejected: %s", e)
            return jsonify({"error": str(e)}), 400
        return jsonify(sim.state_dict())

    return app
