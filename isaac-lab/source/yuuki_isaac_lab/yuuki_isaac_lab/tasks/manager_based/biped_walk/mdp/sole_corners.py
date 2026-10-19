"""足裏の1点の荷重を、DF9-40 の四隅 [N] にバッチで分配する。

`robot_description/sole_pressure.py` と同じ式である。あちらは Hub 用の
1枚ずつ、こちらは学習の全環境を一度に扱う。接触センサは足ごとに
床との合力と平均位置を出すので、入力は圧力中心に置いた1点で足りる。

隅の順は top_left, top_right, bottom_left, bottom_right。
つま先が top、左が left。左右の足で式は同じで、ミラーしない。
"""

from __future__ import annotations

import torch

# sole_pressure.CORNER_KEYS と同じ順。
CORNER_COUNT = 4


def corner_newtons(
    total: torch.Tensor,
    x_cop: torch.Tensor,
    y_cop: torch.Tensor,
    half_x: float,
    half_y: float,
) -> torch.Tensor:
    """合計 [N] と圧力中心 [m] から、四隅の圧縮力 [N] を返す。形は (環境数, 4)。

    ゴムは引っ張れない。負の隅は捨て、残った隅だけで合計と圧力中心を満たすように
    解き直す。4隅から始めて、最大3回落とす。
    """
    if half_x <= 0.0 or half_y <= 0.0:
        raise ValueError("足板の半寸は正である必要があります")
    total = total.reshape(-1)
    x_cop = x_cop.reshape(-1)
    y_cop = y_cop.reshape(-1)
    count_env = total.shape[0]
    device = total.device
    dtype = total.dtype
    places = torch.tensor(
        [[half_x, half_y], [half_x, -half_y], [-half_x, half_y], [-half_x, -half_y]],
        device=device,
        dtype=dtype,
    )
    active = torch.ones(count_env, CORNER_COUNT, device=device, dtype=torch.bool)
    alive = total > 1e-6
    active = active & alive.unsqueeze(-1)
    forces = torch.zeros(count_env, CORNER_COUNT, device=device, dtype=dtype)
    for _ in range(CORNER_COUNT):
        forces = _solve_active(active, total, x_cop, y_cop, places, half_x, half_y)
        # 既に落とした隅は、次の最小を探すときに候補から外す。
        score = torch.where(active, forces, torch.full_like(forces, 1.0e9))
        worst = score.argmin(dim=-1)
        worst_value = forces.gather(1, worst.unsqueeze(-1)).squeeze(-1)
        drop = alive & (worst_value < -1.0e-4 * total.clamp(min=1.0))
        if not bool(drop.any()):
            break
        active[drop, worst[drop]] = False
    return torch.where(active, forces.clamp(min=0.0), torch.zeros_like(forces))


def _solve_active(
    active: torch.Tensor,
    total: torch.Tensor,
    x_cop: torch.Tensor,
    y_cop: torch.Tensor,
    places: torch.Tensor,
    half_x: float,
    half_y: float,
) -> torch.Tensor:
    """いま有効な隅の数に応じて力を求める。無効な隅は 0。"""
    count = active.sum(dim=-1)
    four = _solve_four(total, x_cop, y_cop, half_x, half_y)
    three = _solve_three(active, total, x_cop, y_cop, places)
    two = _solve_two(active, total, x_cop, y_cop, places)
    one = _solve_one(active, total)
    out = torch.zeros_like(four)
    out = torch.where(count.unsqueeze(-1) == 4, four, out)
    out = torch.where(count.unsqueeze(-1) == 3, three, out)
    out = torch.where(count.unsqueeze(-1) == 2, two, out)
    out = torch.where(count.unsqueeze(-1) == 1, one, out)
    return out


def _solve_four(
    total: torch.Tensor,
    x_cop: torch.Tensor,
    y_cop: torch.Tensor,
    half_x: float,
    half_y: float,
) -> torch.Tensor:
    """4隅が全部有効なときの閉じた式。"""
    nx = x_cop / half_x
    ny = y_cop / half_y
    scale = total / 4.0
    return torch.stack(
        (
            scale * (1.0 + nx + ny),
            scale * (1.0 + nx - ny),
            scale * (1.0 - nx + ny),
            scale * (1.0 - nx - ny),
        ),
        dim=-1,
    )


def _solve_one(active: torch.Tensor, total: torch.Tensor) -> torch.Tensor:
    """1隅だけが有効なら、その隅が全部を受ける。"""
    index = active.float().argmax(dim=-1)
    out = torch.zeros(active.shape[0], CORNER_COUNT, device=total.device, dtype=total.dtype)
    return out.scatter(1, index.unsqueeze(-1), total.unsqueeze(-1))


def _solve_two(
    active: torch.Tensor,
    total: torch.Tensor,
    x_cop: torch.Tensor,
    y_cop: torch.Tensor,
    places: torch.Tensor,
) -> torch.Tensor:
    """2隅の線分の上へ圧力中心を下ろす。線分の外は近い隅が全部を受ける。"""
    _, index = torch.topk(active.float(), k=2, dim=-1)
    p0 = places[index[:, 0]]
    p1 = places[index[:, 1]]
    delta = p1 - p0
    length2 = (delta * delta).sum(dim=-1).clamp(min=1.0e-12)
    cop = torch.stack((x_cop, y_cop), dim=-1)
    along = ((cop - p0) * delta).sum(dim=-1) / length2
    along = along.clamp(0.0, 1.0)
    out = torch.zeros(active.shape[0], CORNER_COUNT, device=total.device, dtype=total.dtype)
    out.scatter_(1, index[:, 0:1], (total * (1.0 - along)).unsqueeze(-1))
    out.scatter_(1, index[:, 1:2], (total * along).unsqueeze(-1))
    return out


def _solve_three(
    active: torch.Tensor,
    total: torch.Tensor,
    x_cop: torch.Tensor,
    y_cop: torch.Tensor,
    places: torch.Tensor,
) -> torch.Tensor:
    """3隅の連立。合計と、x・y のモーメントを満たす。"""
    _, index = torch.topk(active.float(), k=3, dim=-1)
    support = places[index]
    ones = torch.ones(support.shape[0], 3, 1, device=total.device, dtype=total.dtype)
    # 列が各隅の (1, x, y)。行が合計・x モーメント・y モーメント。
    matrix = torch.cat((ones, support), dim=-1).transpose(1, 2)
    rhs = torch.stack((total, total * x_cop, total * y_cop), dim=-1)
    count = active.sum(dim=-1)
    eye = torch.eye(3, device=total.device, dtype=total.dtype).expand(matrix.shape[0], 3, 3)
    use_three = count == 3
    matrix = torch.where(use_three[:, None, None], matrix, eye)
    rhs = torch.where(use_three[:, None], rhs, torch.zeros_like(rhs))
    solved = torch.linalg.solve(matrix, rhs)
    out = torch.zeros(active.shape[0], CORNER_COUNT, device=total.device, dtype=total.dtype)
    return out.scatter(1, index, solved)


def _check() -> None:
    """スカラー版と同じ代表例。Isaac は起動しない。"""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[8]
    description = root / "robot_description"
    if str(description) not in sys.path:
        sys.path.insert(0, str(description))
    from sole_pressure import CORNER_KEYS, distribute_newtons

    half_x = 0.10
    half_y = 0.05
    cases = [
        (30.0, 0.0, 0.0),
        (30.0, 0.05, 0.0),
        (30.0, 0.10, 0.05),
        (12.0, -0.04, 0.03),
        (0.0, 0.02, -0.01),
    ]
    totals = torch.tensor([item[0] for item in cases])
    xs = torch.tensor([item[1] for item in cases])
    ys = torch.tensor([item[2] for item in cases])
    batched = corner_newtons(totals, xs, ys, half_x, half_y)
    for row, (total, x_cop, y_cop) in enumerate(cases):
        scalar = distribute_newtons([(x_cop, y_cop, total)], half_x, half_y)
        expected = torch.tensor([scalar[key] for key in CORNER_KEYS])
        if not torch.allclose(batched[row], expected, atol=1.0e-4):
            raise SystemExit(f"corner mismatch row {row}: {batched[row].tolist()} != {expected.tolist()}")
    print("sole_corners ok")


if __name__ == "__main__":
    _check()
