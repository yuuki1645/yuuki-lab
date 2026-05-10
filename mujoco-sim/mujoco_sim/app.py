from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from mujoco_sim.core import Simulation
from mujoco_sim.paths import DEFAULT_MODEL_XML


class StepRequest(BaseModel):
    n: int = Field(default=1, ge=1, le=10_000)
    ctrl: dict[str, float] | None = None


class CtrlRequest(BaseModel):
    ctrl: dict[str, float]


def _model_path() -> Path:
    env = os.environ.get("MUJOCO_SIM_XML")
    if env:
        return Path(env).resolve()
    return DEFAULT_MODEL_XML


@asynccontextmanager
async def lifespan(app: FastAPI):
    xml = _model_path()
    app.state.sim = Simulation(xml_path=xml)
    yield


app = FastAPI(
    title="mujoco-sim",
    version="0.1.0",
    lifespan=lifespan,
)


def get_sim(request: Request) -> Simulation:
    return request.app.state.sim


SimDep = Annotated[Simulation, Depends(get_sim)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/meta")
def meta(sim: SimDep) -> dict[str, Any]:
    return {
        "xml_path": str(sim.xml_path),
        "actuator_names": sim.actuator_names(),
    }


@app.get("/api/state")
def get_state(sim: SimDep) -> dict[str, Any]:
    return sim.state_dict()


@app.post("/api/reset")
def post_reset(sim: SimDep) -> dict[str, Any]:
    sim.reset()
    return sim.state_dict()


@app.post("/api/step")
def post_step(sim: SimDep, body: StepRequest) -> dict[str, Any]:
    try:
        if body.ctrl:
            sim.set_ctrl(body.ctrl)
        sim.step(body.n)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return sim.state_dict()


@app.put("/api/ctrl")
def put_ctrl(sim: SimDep, body: CtrlRequest) -> dict[str, Any]:
    try:
        sim.set_ctrl(body.ctrl)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return sim.state_dict()
