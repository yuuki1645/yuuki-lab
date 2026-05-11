# type: ignore

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import mujoco

from mujoco_realtime_sim.paths import resolved_model_xml


class Simulation:
    """Thread-safe wrapper around MjModel / MjData."""

    def __init__(self, xml_path: Path | None = None) -> None:
        path = xml_path if xml_path is not None else resolved_model_xml()
        if not path.is_file():
            raise FileNotFoundError(f"MJCF not found: {path}")
        self.xml_path = path.resolve()
        self._lock = threading.Lock()
        self.model = mujoco.MjModel.from_xml_path(str(self.xml_path))
        self.data = mujoco.MjData(self.model)
        self._actuator_index: dict[str, int] = {}
        for i in range(self.model.nu):
            name = mujoco.mj_id2name(
                self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, i
            )
            if name:
                self._actuator_index[name] = i

    def reset(self) -> None:
        with self._lock:
            mujoco.mj_resetData(self.model, self.data)
            mujoco.mj_forward(self.model, self.data)

    def set_ctrl(self, values: dict[str, float]) -> None:
        with self._lock:
            for name, val in values.items():
                idx = self._actuator_index.get(name)
                if idx is None:
                    raise KeyError(f"Unknown actuator: {name}")
                self.data.ctrl[idx] = float(val)

    def clear_ctrl(self) -> None:
        with self._lock:
            self.data.ctrl[:] = 0.0

    def step(self, n: int = 1) -> None:
        if n < 1:
            raise ValueError("n must be >= 1")
        with self._lock:
            for _ in range(n):
                mujoco.mj_step(self.model, self.data)

    def sync_viewer(self, viewer: Any) -> None:
        """パッシブ Viewer と共有する model/data の整合のため、ロック下で sync する。"""
        with self._lock:
            viewer.sync()

    def actuator_names(self) -> list[str]:
        return [
            mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
            or f"actuator_{i}"
            for i in range(self.model.nu)
        ]

    def _hinge_joint_angles(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for j in range(self.model.njnt):
            name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, j)
            if not name or name == "root":
                continue
            if self.model.jnt_type[j] != mujoco.mjtJoint.mjJNT_HINGE:
                continue
            qadr = int(self.model.jnt_qposadr[j])
            out[name] = float(self.data.qpos[qadr])
        return out

    def _read_sensor(self, name: str) -> list[float] | None:
        sid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, name)
        if sid < 0:
            return None
        adr = int(self.model.sensor_adr[sid])
        dim = int(self.model.sensor_dim[sid])
        return [float(x) for x in self.data.sensordata[adr : adr + dim]]

    def read_sensor(self, name: str) -> list[float] | None:
        """ロック下で ``sensordata`` のスナップショットを返す（存在しなければ ``None``）。"""
        with self._lock:
            return self._read_sensor(name)

    def state_dict(self) -> dict[str, Any]:
        with self._lock:
            ctrl = {
                mujoco.mj_id2name(
                    self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, i
                )
                or f"actuator_{i}": float(self.data.ctrl[i])
                for i in range(self.model.nu)
            }
            sensors: dict[str, list[float]] = {}
            for s in range(self.model.nsensor):
                sname = mujoco.mj_id2name(
                    self.model, mujoco.mjtObj.mjOBJ_SENSOR, s
                )
                if not sname:
                    continue
                adr = int(self.model.sensor_adr[s])
                dim = int(self.model.sensor_dim[s])
                sensors[sname] = [
                    float(x) for x in self.data.sensordata[adr : adr + dim]
                ]

            return {
                "time": float(self.data.time),
                "qpos": [float(x) for x in self.data.qpos],
                "qvel": [float(x) for x in self.data.qvel],
                "ctrl": ctrl,
                "hinge_joint_rad": self._hinge_joint_angles(),
                "sensors": sensors,
            }
