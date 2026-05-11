import os
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent
XML_DIR = _PACKAGE_ROOT / "xmls"
DEFAULT_MODEL_XML = XML_DIR / "main.xml"


def default_model_path() -> Path:
    return DEFAULT_MODEL_XML


def resolved_model_xml() -> Path:
    """MJCF パス（``MUJOCO_REALTIME_SIM_XML``、なければ ``MUJOCO_SIM_XML``、なければ既定）。"""
    env = os.environ.get("MUJOCO_REALTIME_SIM_XML") or os.environ.get(
        "MUJOCO_SIM_XML"
    )
    if env:
        return Path(env).resolve()
    return DEFAULT_MODEL_XML
