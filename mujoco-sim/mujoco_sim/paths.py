from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent
XML_DIR = _PACKAGE_ROOT / "xmls"
DEFAULT_MODEL_XML = XML_DIR / "main.xml"


def default_model_path() -> Path:
    return DEFAULT_MODEL_XML
