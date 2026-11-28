#!/usr/bin/env python3
"""model_2200 の方策を、CoreS3 が読む C ヘッダにする。

推論は腰の CoreS3 で行う。このスクリプトはメイン PC で一度だけ走らせ、
できた policy_weights.hpp をファームと一緒にサブ PC へ渡す。
サブ PC に Torch は要らない。批評家のネットは出さない。

正本は再生が書いた TorchScript（exported/policy.pt）。
観測の正規化は (x - mean) / (std + 0.01)。0.01 は rsl_rl の既定 eps。
線形層の重みは PyTorch の並び (出力, 入力) の行優先。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch

# 学習の EmpiricalNormalization と同じ。足す値を変えると観測の尺度が変わる。
NORM_EPS = 1.0e-2

# 方策の入力 38、隠れ 128→64、出力 10。ELU は層のあいだにあり、重みは持たない。
OBS = 38
H1 = 128
H2 = 64
ACT = 10

_DEFAULT_PT = (
    Path(__file__).resolve().parents[2]
    / "logs"
    / "rsl_rl"
    / "yuuki_biped_walk"
    / "2026-11-27_14-01-29_stand_half"
    / "exported"
    / "policy.pt"
)
_DEFAULT_OUT = Path(__file__).resolve().parents[1] / "src" / "policy_weights.hpp"


def _as_row(name: str, tensor: torch.Tensor, cols: int) -> np.ndarray:
    """(1, cols) か (cols,) を float32 の一次元にする。"""
    array = tensor.detach().cpu().numpy().astype(np.float32).reshape(-1)
    if array.size != cols:
        raise SystemExit(f"{name} の長さが {array.size}。期待は {cols}。")
    return array


def _as_matrix(name: str, tensor: torch.Tensor, rows: int, cols: int) -> np.ndarray:
    """PyTorch の Linear 重み (出力, 入力) を行優先の float32 にする。"""
    array = tensor.detach().cpu().numpy().astype(np.float32)
    if array.shape != (rows, cols):
        raise SystemExit(f"{name} の形が {array.shape}。期待は {(rows, cols)}。")
    return array.reshape(-1)


def _elu(x: np.ndarray) -> np.ndarray:
    """C 側と同じ ELU。正はそのまま、負は exp(x) - 1。"""
    return np.where(x > 0.0, x, np.exp(x) - 1.0).astype(np.float32)


def _forward_ref(
    obs: np.ndarray,
    mean: np.ndarray,
    std: np.ndarray,
    w0: np.ndarray,
    b0: np.ndarray,
    w1: np.ndarray,
    b1: np.ndarray,
    w2: np.ndarray,
    b2: np.ndarray,
) -> np.ndarray:
    """policy_net.cpp と同じ順。検証用で、実機では使わない。"""
    x = ((obs - mean) / (std + np.float32(NORM_EPS))).astype(np.float32)
    h = _elu(w0.reshape(H1, OBS) @ x + b0)
    h = _elu(w1.reshape(H2, H1) @ h + b1)
    return (w2.reshape(ACT, H2) @ h + b2).astype(np.float32)


def _hex_floats(values: np.ndarray) -> str:
    """float32 を十六進浮動小数で並べる。十進の丸めでビットが変わらない。"""
    parts = []
    flat = values.astype(np.float32).reshape(-1)
    for i, value in enumerate(flat):
        # Python の float は float32 を正確に保持できる。
        # 接尾の f で float。十六進なので float32 のビットを保ったまま代入できる。
        parts.append(float(np.float32(value)).hex() + "f")
        if (i + 1) % 8 == 0:
            parts.append(",\n    ")
        else:
            parts.append(", ")
    text = "".join(parts).rstrip(", \n")
    return text


def _c_array(name: str, values: np.ndarray) -> str:
    count = int(values.size)
    return (
        f"static const float {name}[{count}] = {{\n    "
        f"{_hex_floats(values)}\n}};"
    )


def _load(path: Path) -> dict[str, np.ndarray]:
    """TorchScript から方策の平均・分散と 3 つの線形層だけを取る。"""
    module = torch.jit.load(str(path), map_location="cpu")
    module.eval()
    state = module.state_dict()
    need = {
        "obs_normalizer._mean": OBS,
        "obs_normalizer._std": OBS,
        "mlp.0.weight": (H1, OBS),
        "mlp.0.bias": H1,
        "mlp.2.weight": (H2, H1),
        "mlp.2.bias": H2,
        "mlp.4.weight": (ACT, H2),
        "mlp.4.bias": ACT,
    }
    missing = [key for key in need if key not in state]
    if missing:
        found = ", ".join(sorted(state.keys()))
        raise SystemExit(f"重みの名前が違う: {missing}\n実際: {found}")

    arrays = {
        "mean": _as_row("mean", state["obs_normalizer._mean"], OBS),
        "std": _as_row("std", state["obs_normalizer._std"], OBS),
        "w0": _as_matrix("w0", state["mlp.0.weight"], H1, OBS),
        "b0": _as_row("b0", state["mlp.0.bias"], H1),
        "w1": _as_matrix("w1", state["mlp.2.weight"], H2, H1),
        "b1": _as_row("b1", state["mlp.2.bias"], H2),
        "w2": _as_matrix("w2", state["mlp.4.weight"], ACT, H2),
        "b2": _as_row("b2", state["mlp.4.bias"], ACT),
    }
    return {"module": module, **arrays}


def _check(loaded: dict) -> tuple[np.ndarray, np.ndarray]:
    """ゼロ観測と、重力 z = -1 の観測で、Torch と C と同じ式を比べる。"""
    module = loaded["module"]
    arrays = {key: loaded[key] for key in ("mean", "std", "w0", "b0", "w1", "b1", "w2", "b2")}

    zeros = np.zeros(OBS, dtype=np.float32)
    stand = np.zeros(OBS, dtype=np.float32)
    # 観測 10..12 が体座標の重力。直立は z が約 -1。
    stand[12] = np.float32(-1.0)
    # 位相の cos。角度 0 のときの値。
    stand[25] = np.float32(1.0)

    samples = []
    with torch.no_grad():
        for obs in (zeros, stand):
            tensor = torch.from_numpy(obs).unsqueeze(0)
            out = module(tensor)
            if isinstance(out, (tuple, list)):
                out = out[0]
            torch_y = out.detach().cpu().numpy().astype(np.float32).reshape(-1)
            ref_y = _forward_ref(obs, **arrays)
            if torch_y.shape != (ACT,) or not np.all(np.isfinite(torch_y)):
                raise SystemExit(f"Torch の出力が不正: {torch_y}")
            err = float(np.max(np.abs(torch_y - ref_y)))
            if err > 1.0e-4:
                raise SystemExit(f"C と同じ式との差が {err}。重みの並びを確認する。")
            samples.append(torch_y)
    return samples[0], samples[1]


def _fmt_row(values: np.ndarray) -> str:
    return ", ".join(f"{float(v): .6f}" for v in values)


def write_header(path: Path, loaded: dict, zero_y: np.ndarray, stand_y: np.ndarray, source: Path) -> None:
    """フラッシュに置く定数。手で直さない。作り直すときはこのスクリプト。"""
    text = f"""#pragma once

/**
 * 歩行方策の重み。手で編集しない。
 *
 * 元: {source.as_posix()}
 * 学習: 2026-11-27_14-01-29_stand_half の model_2200。
 * 中身は方策だけ。批評家は学習用なので載せていない。
 * 正規化は (観測 - 平均) / (標準偏差 + kPolicyNormEps)。
 * kPolicyNormEps は rsl_rl EmpiricalNormalization の既定 0.01。
 * 重みは PyTorch Linear の (出力, 入力) を行優先にしたもの。
 *
 * 書き出し時の照合（Torch と、C と同じ行列積）:
 *   観測ゼロ → {_fmt_row(zero_y)}
 *   直立の重力と位相 → {_fmt_row(stand_y)}
 */

static constexpr int kPolicyObs = {OBS};
static constexpr int kPolicyHidden1 = {H1};
static constexpr int kPolicyHidden2 = {H2};
static constexpr int kPolicyAct = {ACT};
static constexpr float kPolicyNormEps = {NORM_EPS:.2e}f;

{_c_array("kPolicyObsMean", loaded["mean"])}

{_c_array("kPolicyObsStd", loaded["std"])}

{_c_array("kPolicyW0", loaded["w0"])}

{_c_array("kPolicyB0", loaded["b0"])}

{_c_array("kPolicyW1", loaded["w1"])}

{_c_array("kPolicyB1", loaded["b1"])}

{_c_array("kPolicyW2", loaded["w2"])}

{_c_array("kPolicyB2", loaded["b2"])}
"""
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="方策の TorchScript を C ヘッダにする")
    parser.add_argument("--pt", type=Path, default=_DEFAULT_PT, help="exported/policy.pt")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT, help="policy_weights.hpp")
    args = parser.parse_args()
    if not args.pt.is_file():
        raise SystemExit(f"方策ファイルが無い: {args.pt}")
    loaded = _load(args.pt)
    zero_y, stand_y = _check(loaded)
    write_header(args.out, loaded, zero_y, stand_y, args.pt)
    print(f"wrote {args.out}")
    print("zero ", _fmt_row(zero_y))
    print("stand", _fmt_row(stand_y))


if __name__ == "__main__":
    main()
