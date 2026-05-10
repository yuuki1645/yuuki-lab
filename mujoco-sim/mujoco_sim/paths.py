import os
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent
XML_DIR = _PACKAGE_ROOT / "xmls"
DEFAULT_MODEL_XML = XML_DIR / "main.xml"


def default_model_path() -> Path:
    return DEFAULT_MODEL_XML


def resolved_model_xml() -> Path:
    """MJCF パス（環境変数 MUJOCO_SIM_XML があれば優先）。"""
    env = os.environ.get("MUJOCO_SIM_XML")
    if env:
        return Path(env).resolve()
    return DEFAULT_MODEL_XML
