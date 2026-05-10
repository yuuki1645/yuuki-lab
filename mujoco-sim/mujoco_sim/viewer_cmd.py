"""Passive viewer for the packaged model (no HTTP server)."""

from __future__ import annotations

import time

import mujoco
import mujoco.viewer

from mujoco_sim.paths import DEFAULT_MODEL_XML


def main() -> None:
    path = DEFAULT_MODEL_XML
    model = mujoco.MjModel.from_xml_path(str(path))
    data = mujoco.MjData(model)
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(model.opt.timestep)


if __name__ == "__main__":
    main()
