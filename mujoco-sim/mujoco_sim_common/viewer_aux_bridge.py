# type: ignore
"""MuJoCo passive viewer と並行して動かす HTTP ブリッジ。

Robotics Hub の「MuJoCo ビュワー補助」ページから、シミュレーション状態の取得・
再生制御・MuJoCo 表示オプションの変更を行うための API を提供する。

``mujoco_test_009.py`` がメインスレッドで ``launch_passive`` ループを回しつつ、
本モジュールの ``ViewerAuxRuntime`` を共有し、Flask は別スレッドで待ち受ける。
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import mujoco
from flask import Flask, jsonify, request
from flask_cors import CORS

LOG = logging.getLogger("mujoco_sim_common.viewer_aux")

_VIS_FLAG_NAMES: tuple[str, ...] = tuple(
    n
    for n in dir(mujoco.mjtVisFlag)
    if n.startswith("mjVIS_") and n != "mjVISSTRING"
)

_FRAME_NAMES: tuple[str, ...] = tuple(
    n for n in dir(mujoco.mjtFrame) if n.startswith("mjFRAME_")
)
_LABEL_NAMES: tuple[str, ...] = tuple(
    n for n in dir(mujoco.mjtLabel) if n.startswith("mjLABEL_")
)


def _body_name(model: mujoco.MjModel, bid: int) -> str:
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, bid) or f"body_{bid}"


def _joint_name(model: mujoco.MjModel, jid: int) -> str:
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, jid) or f"joint_{jid}"


def _geom_name(model: mujoco.MjModel, gid: int) -> str:
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, gid) or f"geom_{gid}"


def _actuator_name(model: mujoco.MjModel, uid: int) -> str:
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, uid) or f"actuator_{uid}"


def _site_name(model: mujoco.MjModel, sid: int) -> str:
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SITE, sid) or f"site_{sid}"


def _joint_type_str(jt: int) -> str:
    mapping = {
        int(mujoco.mjtJoint.mjJNT_FREE): "free",
        int(mujoco.mjtJoint.mjJNT_BALL): "ball",
        int(mujoco.mjtJoint.mjJNT_SLIDE): "slide",
        int(mujoco.mjtJoint.mjJNT_HINGE): "hinge",
    }
    return mapping.get(int(jt), str(int(jt)))


@dataclass
class ViewerAuxRuntime:
    """メインスレッド（viewer ループ）と Flask スレッドで共有する状態。"""

    model: mujoco.MjModel
    data: mujoco.MjData
    xml_path: str
    lock: threading.Lock = field(default_factory=threading.Lock)
    paused: bool = False
    speed: float = 1.0
    step_count: int = 0
    _cmd_q: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue)
    _pending_vis: dict[int, int] = field(default_factory=dict)
    _pending_frame: int | None = None
    _pending_label: int | None = None
    _flags_snapshot: list[int] = field(default_factory=list)
    _viewer_ref: list[Any] = field(default_factory=list)  # single-element holder for Handle

    def attach_viewer_handle(self, viewer: Any) -> None:
        self._viewer_ref.clear()
        self._viewer_ref.append(viewer)
        with self.lock:
            self._flags_snapshot = [int(x) for x in viewer.opt.flags]

    def _viewer(self) -> Any | None:
        return self._viewer_ref[0] if self._viewer_ref else None

    def enqueue(self, cmd: dict[str, Any]) -> None:
        self._cmd_q.put(cmd)

    def _apply_commands_unlocked(self, viewer: Any | None) -> None:
        while True:
            try:
                cmd = self._cmd_q.get_nowait()
            except queue.Empty:
                break
            op = cmd.get("op")
            if op == "pause":
                self.paused = True
            elif op in ("play", "resume"):
                self.paused = False
            elif op == "reset":
                mujoco.mj_resetData(self.model, self.data)
                mujoco.mj_forward(self.model, self.data)
                self.step_count = 0
            elif op == "restart":
                mujoco.mj_resetData(self.model, self.data)
                mujoco.mj_forward(self.model, self.data)
                self.step_count = 0
                self.paused = False
            elif op == "set_speed":
                s = float(cmd.get("value", 1.0))
                if s < 0.05:
                    s = 0.05
                if s > 8.0:
                    s = 8.0
                self.speed = s
            elif op == "step_once":
                if self.paused:
                    mujoco.mj_step(self.model, self.data)
                    self.step_count += 1
            elif op == "set_vis_flag":
                idx = int(cmd["index"])
                val = 1 if bool(cmd.get("value")) else 0
                self._pending_vis[idx] = val
            elif op == "set_frame":
                self._pending_frame = int(cmd["value"])
            elif op == "set_label":
                self._pending_label = int(cmd["value"])
            else:
                LOG.warning("unknown viewer_aux op: %r", op)

        for idx, val in self._pending_vis.items():
            if viewer is not None and 0 <= idx < len(viewer.opt.flags):
                viewer.opt.flags[idx] = int(val)
        self._pending_vis.clear()

        if viewer is not None:
            if self._pending_frame is not None:
                viewer.opt.frame = int(self._pending_frame)
                self._pending_frame = None
            if self._pending_label is not None:
                viewer.opt.label = int(self._pending_label)
                self._pending_label = None
            self._flags_snapshot = [int(x) for x in viewer.opt.flags]

    def main_tick(self, viewer: Any | None) -> None:
        """メインループの先頭でロック取得のまま呼ぶ。"""
        with self.lock:
            self._apply_commands_unlocked(viewer)
            if not self.paused:
                mujoco.mj_step(self.model, self.data)
                self.step_count += 1
            if viewer is not None:
                viewer.sync()

    def main_tick_paused_sync_only(self, viewer: Any | None) -> None:
        """一時停止中: コマンド適用と viewer のみ。"""
        with self.lock:
            self._apply_commands_unlocked(viewer)
            if viewer is not None:
                viewer.sync()

    def sleep_after_tick(self) -> None:
        dt = float(self.model.opt.timestep)
        if dt <= 0:
            dt = 0.002
        s = max(0.05, float(self.speed))
        delay = dt / s
        if self.paused:
            delay = min(0.05, max(delay, 1.0 / 60.0))
        time.sleep(delay)

    def build_snapshot(self, detail: str = "standard") -> dict[str, Any]:
        detail = (detail or "standard").lower()
        if detail not in ("minimal", "standard", "full"):
            detail = "standard"
        with self.lock:
            m, d = self.model, self.data
            snap: dict[str, Any] = {
                "xml_path": self.xml_path,
                "sim_time": float(d.time),
                "timestep": float(m.opt.timestep),
                "step_count": int(self.step_count),
                "paused": bool(self.paused),
                "speed": float(self.speed),
                "nq": int(m.nq),
                "nv": int(m.nv),
                "nu": int(m.nu),
                "nbody": int(m.nbody),
                "njnt": int(m.njnt),
                "ngeom": int(m.ngeom),
                "nsite": int(m.nsite),
                "ncon": int(d.ncon),
                "qpos": [float(x) for x in d.qpos],
                "qvel": [float(x) for x in d.qvel],
                "ctrl": [float(d.ctrl[i]) for i in range(m.nu)],
                "act": [float(d.act[i]) for i in range(m.na)] if m.na else [],
            }
            if detail in ("standard", "full"):
                bodies = []
                for i in range(m.nbody):
                    bodies.append(
                        {
                            "id": i,
                            "name": _body_name(m, i),
                            "xpos": [float(x) for x in d.xpos[i]],
                            "xquat": [float(x) for x in d.xquat[i]],
                            "cvel": [float(x) for x in d.cvel[i]],
                        }
                    )
                snap["bodies"] = bodies
                joints = []
                for j in range(m.njnt):
                    qadr = int(m.jnt_qposadr[j])
                    vadr = int(m.jnt_dofadr[j])
                    jt = int(m.jnt_type[j])
                    if j + 1 < m.njnt:
                        nq_i = int(m.jnt_qposadr[j + 1] - qadr)
                        nv_i = int(m.jnt_dofadr[j + 1] - vadr)
                    else:
                        nq_i = int(m.nq - qadr)
                        nv_i = int(m.nv - vadr)
                    qslice = [float(d.qpos[qadr + k]) for k in range(nq_i)]
                    vslice = [float(d.qvel[vadr + k]) for k in range(nv_i)]
                    joints.append(
                        {
                            "id": j,
                            "name": _joint_name(m, j),
                            "type": _joint_type_str(jt),
                            "qpos_adr": qadr,
                            "dof_adr": vadr,
                            "qpos": qslice,
                            "qvel": vslice,
                        }
                    )
                snap["joints"] = joints
                snap["actuator_names"] = [
                    _actuator_name(m, i) for i in range(m.nu)
                ]
                snap["qfrc_actuator"] = [
                    float(d.qfrc_actuator[i]) for i in range(m.nv)
                ]
            if detail == "full":
                geoms = []
                for g in range(m.ngeom):
                    geoms.append(
                        {
                            "id": g,
                            "name": _geom_name(m, g),
                            "body": int(m.geom_bodyid[g]),
                            "xpos": [float(x) for x in d.geom_xpos[g]],
                            "xmat": [float(x) for x in d.geom_xmat[g]],
                        }
                    )
                snap["geoms"] = geoms
                sites = []
                for s_i in range(m.nsite):
                    sites.append(
                        {
                            "id": s_i,
                            "name": _site_name(m, s_i),
                            "body": int(m.site_bodyid[s_i]),
                            "xpos": [float(x) for x in d.site_xpos[s_i]],
                            "xmat": [float(x) for x in d.site_xmat[s_i]],
                        }
                    )
                snap["sites"] = sites
                contacts = []
                for k in range(d.ncon):
                    c = d.contact[k]
                    contacts.append(
                        {
                            "dist": float(c.dist),
                            "pos": [float(x) for x in c.pos],
                            "geom1": int(c.geom1),
                            "geom2": int(c.geom2),
                            "geom1_name": _geom_name(m, int(c.geom1)),
                            "geom2_name": _geom_name(m, int(c.geom2)),
                        }
                    )
                snap["contacts"] = contacts
                sensors: dict[str, list[float]] = {}
                for s in range(m.nsensor):
                    sname = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_SENSOR, s)
                    if not sname:
                        continue
                    adr = int(m.sensor_adr[s])
                    dim = int(m.sensor_dim[s])
                    sensors[sname] = [
                        float(x) for x in d.sensordata[adr : adr + dim]
                    ]
                snap["sensors"] = sensors
            return snap

    def display_state(self) -> dict[str, Any]:
        with self.lock:
            viewer = self._viewer()
            flags_meta = [
                {"name": n, "index": int(getattr(mujoco.mjtVisFlag, n)), "on": 0}
                for n in _VIS_FLAG_NAMES
            ]
            for item in flags_meta:
                i = item["index"]
                if i < len(self._flags_snapshot):
                    item["on"] = int(self._flags_snapshot[i])
            frame = int(viewer.opt.frame) if viewer else 0
            label = int(viewer.opt.label) if viewer else 0
            return {
                "vis_flags": flags_meta,
                "frame": frame,
                "frame_name": self._enum_name(mujoco.mjtFrame, frame, "mjFRAME_NONE"),
                "label": label,
                "label_name": self._enum_name(mujoco.mjtLabel, label, "mjLABEL_NONE"),
                "frame_choices": list(_FRAME_NAMES),
                "label_choices": list(_LABEL_NAMES),
                "vis_flag_names": list(_VIS_FLAG_NAMES),
            }

    @staticmethod
    def _enum_name(enum_cls: Any, value: int, default: str) -> str:
        for n in dir(enum_cls):
            if n.startswith("mj"):
                try:
                    if int(getattr(enum_cls, n)) == int(value):
                        return n
                except Exception:
                    continue
        return default


def create_viewer_aux_app(get_runtime: Callable[[], ViewerAuxRuntime]) -> Flask:
    app = Flask(__name__)
    CORS(app)

    @app.route("/health", methods=["GET"])
    def health() -> Any:
        return jsonify({"status": "ok", "role": "mujoco_viewer_aux"})

    @app.route("/api/viewer/snapshot", methods=["GET"])
    def snapshot() -> Any:
        rt = get_runtime()
        detail = request.args.get("detail", "standard")
        return jsonify(rt.build_snapshot(detail=str(detail)))

    @app.route("/api/viewer/status", methods=["GET"])
    def status() -> Any:
        rt = get_runtime()
        with rt.lock:
            return jsonify(
                {
                    "xml_path": rt.xml_path,
                    "sim_time": float(rt.data.time),
                    "timestep": float(rt.model.opt.timestep),
                    "step_count": int(rt.step_count),
                    "paused": bool(rt.paused),
                    "speed": float(rt.speed),
                    "viewer_open": rt._viewer() is not None,
                }
            )

    @app.route("/api/viewer/display", methods=["GET"])
    def display_get() -> Any:
        rt = get_runtime()
        return jsonify(rt.display_state())

    @app.route("/api/viewer/display", methods=["POST"])
    def display_post() -> Any:
        rt = get_runtime()
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object expected"}), 400
        if "vis_flag" in body and isinstance(body["vis_flag"], dict):
            for k, v in body["vis_flag"].items():
                ks = str(k)
                if ks.startswith("mj"):
                    idx = int(getattr(mujoco.mjtVisFlag, ks))
                else:
                    idx = int(k)
                rt.enqueue({"op": "set_vis_flag", "index": idx, "value": bool(v)})
        if "frame" in body:
            fn = str(body["frame"])
            try:
                fv = int(getattr(mujoco.mjtFrame, fn))
            except AttributeError:
                return jsonify({"error": f"unknown frame {fn!r}"}), 400
            rt.enqueue({"op": "set_frame", "value": fv})
        if "label" in body:
            ln = str(body["label"])
            try:
                lv = int(getattr(mujoco.mjtLabel, ln))
            except AttributeError:
                return jsonify({"error": f"unknown label {ln!r}"}), 400
            rt.enqueue({"op": "set_label", "value": lv})
        return jsonify({"status": "ok"})

    @app.route("/api/viewer/control", methods=["POST"])
    def control() -> Any:
        rt = get_runtime()
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object expected"}), 400
        action = body.get("action")
        if not isinstance(action, str):
            return jsonify({"error": "action (string) is required"}), 400
        a = action.lower().strip()
        if a in ("pause", "stop"):
            rt.enqueue({"op": "pause"})
        elif a in ("play", "resume"):
            rt.enqueue({"op": "resume"})
        elif a == "reset":
            rt.enqueue({"op": "reset"})
        elif a in ("restart", "reset_play"):
            rt.enqueue({"op": "restart"})
        elif a in ("step", "step_once"):
            rt.enqueue({"op": "step_once"})
        elif a == "set_speed":
            if "value" not in body:
                return jsonify({"error": "value is required for set_speed"}), 400
            rt.enqueue({"op": "set_speed", "value": float(body["value"])})
        else:
            return jsonify({"error": f"unknown action: {action!r}"}), 400
        return jsonify({"status": "ok", "action": a})

    return app


def start_viewer_aux_http(
    runtime: ViewerAuxRuntime,
    host: str = "0.0.0.0",
    port: int = 8788,
    quiet: bool = False,
) -> threading.Thread:
    """デーモンスレッドで Flask を起動する。``runtime`` は同一プロセスで共有。"""

    app = create_viewer_aux_app(lambda: runtime)
    if quiet:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

    def run() -> None:
        app.run(
            host=host,
            port=port,
            threaded=True,
            use_reloader=False,
        )

    th = threading.Thread(target=run, name="viewer-aux-http", daemon=True)
    th.start()
    LOG.info("viewer aux HTTP on http://%s:%s", host, port)
    return th
