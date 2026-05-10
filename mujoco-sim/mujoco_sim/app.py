# type: ignore

from __future__ import annotations

import logging
import math
from typing import Any

from flask import Flask, current_app, jsonify, request
from flask_cors import CORS

from mujoco_sim.core import Simulation
from mujoco_sim.kinematics import KINEMATICS, kinematics_by_joint
from mujoco_sim.realtime import RealtimeStepper

LOG = logging.getLogger("mujoco_sim.api")

CTRL_MODES = ("rad", "deg", "logical")
_LOG_BODY_PATHS = ("/api/set", "/api/set_multiple", "/api/ctrl")


def _get_sim() -> Simulation:
    return current_app.extensions["simulation"]


def _get_stepper() -> RealtimeStepper | None:
    return current_app.extensions.get("realtime_stepper")


def _convert_to_rad(angles: dict, mode: str) -> dict[str, float]:
    """`{actuator_name: angle}` を MuJoCo の ctrl 単位（rad）に正規化する。

    - ``mode == "rad"``（既定）: そのまま float 化。
    - ``mode == "deg"``: 各値を度→ラジアンに換算。
    - ``mode == "logical"``: ``kinematics.KINEMATICS`` を引いて
      論理角(度)→MuJoCo関節角(度)→ラジアン と 2 段で換算。
    - 不正な mode は ``ValueError``、辞書でない場合は ``TypeError``、
      ``logical`` で kinematics 未登録のアクチュエータは ``KeyError``。
    """

    if not isinstance(angles, dict):
        raise TypeError("angles must be an object mapping names to numbers")
    if mode not in CTRL_MODES:
        raise ValueError(
            f"mode must be one of {CTRL_MODES} (got {mode!r})"
        )

    if mode == "logical":
        out: dict[str, float] = {}
        for name, val in angles.items():
            kin = KINEMATICS.get(str(name))
            if kin is None:
                raise KeyError(
                    f"No logical kinematics for actuator: {name!r}"
                )
            mujoco_deg = kin.logical_to_mujoco_deg(float(val))
            out[str(name)] = math.radians(mujoco_deg)
        return out

    if mode == "deg":
        return {str(k): math.radians(float(v)) for k, v in angles.items()}
    return {str(k): float(v) for k, v in angles.items()}


def _state_with_logical(state: dict) -> dict:
    """``Simulation.state_dict()`` の戻り値に ``logical_deg`` を追加する。

    ``hinge_joint_rad`` から各サーボの論理角を計算して、アクチュエータ名を
    キーとした辞書として載せる。kinematics 未登録の関節は無視する。
    """

    hinge_rad: dict[str, float] = state.get("hinge_joint_rad") or {}
    by_joint = kinematics_by_joint()
    logical_deg: dict[str, float] = {}
    for joint_name, rad in hinge_rad.items():
        kin = by_joint.get(joint_name)
        if kin is None:
            continue
        mujoco_deg = math.degrees(float(rad))
        logical_deg[kin.actuator] = kin.mujoco_deg_to_logical(mujoco_deg)
    return {**state, "logical_deg": logical_deg}


def create_app(
    simulation: Simulation | None = None,
    stepper: RealtimeStepper | None = None,
) -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.extensions["simulation"] = simulation or Simulation()
    if stepper is not None:
        app.extensions["realtime_stepper"] = stepper

    @app.before_request
    def _log_request() -> None:
        path = request.path
        if path != "/health" and not path.startswith("/api"):
            return
        client = request.remote_addr or "?"
        detail = ""
        if request.method in ("POST", "PUT") and path in _LOG_BODY_PATHS:
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
        st = _get_stepper()
        logical_meta = {
            kin.actuator: {
                "joint": kin.joint,
                "lo": kin.logical_lo,
                "hi": kin.logical_hi,
                "default": kin.default_logical,
                "sign": kin.sign,
                "offset_deg": kin.offset_deg,
            }
            for kin in KINEMATICS.values()
        }
        return jsonify(
            {
                "xml_path": str(sim.xml_path),
                "actuator_names": sim.actuator_names(),
                "timestep": float(sim.model.opt.timestep),
                "realtime": {
                    "running": bool(st and st.is_running),
                    "paused": bool(st and st.is_paused),
                },
                "logical": logical_meta,
            }
        )

    @app.route("/api/state", methods=["GET"])
    def get_state() -> Any:
        return jsonify(_state_with_logical(_get_sim().state_dict()))

    @app.route("/api/reset", methods=["POST"])
    def post_reset() -> Any:
        sim = _get_sim()
        sim.reset()
        return jsonify(_state_with_logical(sim.state_dict()))

    @app.route("/api/step", methods=["POST"])
    def post_step_gone() -> Any:
        # 旧 API。サーバ側が常時 mj_step を回す方式に移行したため廃止。
        return (
            jsonify(
                {
                    "error": (
                        "POST /api/step is removed. The server now advances "
                        "the simulation in real time on its own; send servo "
                        "targets via POST /api/set or POST /api/set_multiple."
                    )
                }
            ),
            410,
        )

    @app.route("/api/set", methods=["POST"])
    def post_set() -> Any:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object expected"}), 400
        actuator = body.get("actuator")
        if not isinstance(actuator, str) or not actuator:
            return jsonify({"error": "actuator (string) is required"}), 400
        if "angle" not in body:
            return jsonify({"error": "angle is required"}), 400

        sim = _get_sim()
        try:
            ctrl_rad = _convert_to_rad(
                {actuator: body["angle"]}, body.get("mode", "rad")
            )
            sim.set_ctrl(ctrl_rad)
        except (KeyError, TypeError, ValueError) as e:
            LOG.warning("POST /api/set rejected: %s", e)
            return jsonify({"error": str(e)}), 400

        rad_value = ctrl_rad[actuator]
        deg_value = math.degrees(rad_value)
        kin = KINEMATICS.get(actuator)
        logical_value = kin.mujoco_deg_to_logical(deg_value) if kin else None
        return jsonify(
            {
                "status": "ok",
                "actuator": actuator,
                "rad": rad_value,
                "deg": deg_value,
                "logical": logical_value,
            }
        )

    @app.route("/api/set_multiple", methods=["POST"])
    def post_set_multiple() -> Any:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object expected"}), 400
        angles = body.get("angles")
        if not isinstance(angles, dict) or not angles:
            return jsonify({"error": "angles (object) is required"}), 400

        sim = _get_sim()
        try:
            ctrl_rad = _convert_to_rad(angles, body.get("mode", "rad"))
            sim.set_ctrl(ctrl_rad)
        except (KeyError, TypeError, ValueError) as e:
            LOG.warning("POST /api/set_multiple rejected: %s", e)
            return jsonify({"error": str(e)}), 400

        return jsonify({"status": "ok", "applied": len(ctrl_rad)})

    @app.route("/api/ctrl", methods=["PUT"])
    def put_ctrl() -> Any:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object expected"}), 400
        ctrl = body.get("ctrl")
        if not isinstance(ctrl, dict) or not ctrl:
            return jsonify({"error": "ctrl object required"}), 400

        sim = _get_sim()
        try:
            ctrl_rad = _convert_to_rad(ctrl, body.get("mode", "rad"))
            sim.set_ctrl(ctrl_rad)
        except (KeyError, TypeError, ValueError) as e:
            LOG.warning("PUT /api/ctrl rejected: %s", e)
            return jsonify({"error": str(e)}), 400
        return jsonify({"status": "ok", "applied": len(ctrl_rad)})

    @app.route("/api/pause", methods=["POST"])
    def post_pause() -> Any:
        st = _get_stepper()
        if st is None:
            return jsonify({"error": "realtime stepper is not running"}), 400
        st.pause()
        return jsonify({"status": "paused"})

    @app.route("/api/resume", methods=["POST"])
    def post_resume() -> Any:
        st = _get_stepper()
        if st is None:
            return jsonify({"error": "realtime stepper is not running"}), 400
        st.resume()
        return jsonify({"status": "running"})

    return app
