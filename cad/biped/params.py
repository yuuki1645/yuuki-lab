"""yuuki_biped.yaml を、URDF 生成と同じ関数で読む。

寸法の数字はこのファイルに書かない。軸間が null のときの式や、
電池のダンボール寸法も generate_urdf.resolve_params に任せる。
"""

from __future__ import annotations

import sys
from pathlib import Path

# cad/biped/params.py → リポジトリルートは2つ上。
REPO_ROOT = Path(__file__).resolve().parents[2]
YAML_PATH = REPO_ROOT / "robot_description" / "yuuki_biped.yaml"
# generate_urdf.py はパッケージではない。隣の model_size を import できるよう、
# このディレクトリをパスに足す。CAD 側は generate() を呼ばないので model_size は不要。
_GENERATOR_DIR = REPO_ROOT / "robot_description"


def generator():
    """robot_description/generate_urdf.py を読み込む。"""
    if str(_GENERATOR_DIR) not in sys.path:
        sys.path.insert(0, str(_GENERATOR_DIR))
    import generate_urdf

    return generate_urdf


def load_raw(path: Path | None = None) -> dict:
    """yaml を辞書のまま返す。単位の解釈はまだしない。"""
    import yaml

    yaml_path = YAML_PATH if path is None else path
    with yaml_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"設定が辞書ではありません: {yaml_path}")
    return raw


def load_params(path: Path | None = None) -> dict:
    """null を埋めたパラメータ。角度はラジアン。"""
    return generator().resolve_params(load_raw(path))


def load_model(path: Path | None = None):
    """パラメータと、全関節 0 のリンク・関節。

    戻り値の links / joints は generate_urdf の Link と Joint。
    箱の中心はまだ各リンクの座標で、世界座標ではない。
    """
    gen = generator()
    params = gen.resolve_params(load_raw(path))
    links, joints = gen.build_model(params)
    return params, links, joints
