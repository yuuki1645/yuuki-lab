"""足裏の接触を、DF9-40 四隅の kg に分配する。

Isaac Sim も実機の画面も、このモジュールの辞書をそのまま使う。
PhysX は足板と床の接触点（位置と力積）までしか出さない。実機のセンサは
床に触れておらず、二重底の板が四隅のゴムへ分けた圧縮力を測る。
ここではその分配だけを行う。

座標系は足裏下面の中心。x がつま先、y が左、力は上向きの圧縮 [N]。
センサは足板の四隅にあるものとして扱う。実測の取り付け位置が分かったら
PLATE_HALF_X_M / PLATE_HALF_Y_M を、中心からセンサまでの距離に替える。

四隅がすべて押し込まれているときは、硬い板を同じばね4本で支えた解を使う。

    つま先左 = F/4 * (1 + x̄/a + ȳ/b)
    つま先右 = F/4 * (1 + x̄/a - ȳ/b)
    かかと左 = F/4 * (1 - x̄/a + ȳ/b)
    かかと右 = F/4 * (1 - x̄/a - ȳ/b)

ゴムは引っ張れない。負になった隅は 0 にして、残りの隅だけで
合計と圧力中心が合うように解き直す。
"""

from __future__ import annotations

# 足板 0.300 m × 0.170 m の半寸。URDF の foot.size_m と揃える。
PLATE_HALF_X_M = 0.150
PLATE_HALF_Y_M = 0.085
# シミュの重力 9.81 と揃える。DF9-40 のデータシートの「kg」はこの力。
GRAVITY_MPS2 = 9.81
# データシートの満量。画面の色もこの 2 kg を 100% にする。
DF9_MAX_KG = 2.0
# 応答点はおおよそ 20 g。これ未満は 0 にして、床の数値ノイズを出さない。
DEADZONE_KG = 0.02

# Hub の RightFootSole と同じ名前。つま先が top、左が left。
CORNER_KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")


def sample_from_points(
    points: list[tuple[float, float, float]],
    seq: int,
    *,
    ok: bool = True,
) -> dict:
    """接触点 (x[m], y[m], 圧縮[N]) から、Hub の足裏1枚分の辞書を作る。

    ok が False のときはセンサ自体が無い。中身は 0 で、画面は「未検出」になる。
    点が空でも ok なら、接続されたセンサが 0 kg を読んでいる状態にする。
    """
    newtons = {key: 0.0 for key in CORNER_KEYS}
    if ok and points:
        newtons = distribute_newtons(points, PLATE_HALF_X_M, PLATE_HALF_Y_M)

    corners: dict[str, dict | None] = {}
    total = 0.0
    for key in CORNER_KEYS:
        kg = _to_kg(newtons[key]) if ok else 0.0
        total += kg
        corners[key] = {
            "force_kg": kg,
            "force_pct": 100.0 * kg / DF9_MAX_KG,
        }
    return {
        "ok": bool(ok),
        "seq": int(seq),
        "mask": 0b1111 if ok else 0,
        "force_kg": total,
        "corners": corners,
    }


def distribute_newtons(
    points: list[tuple[float, float, float]],
    half_x: float,
    half_y: float,
) -> dict[str, float]:
    """接触点の垂直荷重を、四隅の圧縮力 [N] にする。負の隅は捨てて解き直す。"""
    zeros = {key: 0.0 for key in CORNER_KEYS}
    usable = [(x, y, f) for x, y, f in points if f > 0.0]
    total = sum(f for _, _, f in usable)
    if total <= 1e-6 or half_x <= 0.0 or half_y <= 0.0:
        return zeros

    x_cop = sum(x * f for x, y, f in usable) / total
    y_cop = sum(y * f for x, y, f in usable) / total
    places = {
        "top_left": (half_x, half_y),
        "top_right": (half_x, -half_y),
        "bottom_left": (-half_x, half_y),
        "bottom_right": (-half_x, -half_y),
    }
    active = list(CORNER_KEYS)
    while active:
        solved = _solve_supports(active, places, total, x_cop, y_cop, half_x, half_y)
        if solved is None:
            nearest = min(
                active,
                key=lambda key: (places[key][0] - x_cop) ** 2 + (places[key][1] - y_cop) ** 2,
            )
            return {key: (total if key == nearest else 0.0) for key in CORNER_KEYS}
        negative = [key for key in active if solved[key] < -1e-4 * max(total, 1.0)]
        if not negative:
            return {key: max(0.0, solved.get(key, 0.0)) for key in CORNER_KEYS}
        active.remove(min(negative, key=lambda key: solved[key]))
    return zeros


def _solve_supports(
    active: list[str],
    places: dict[str, tuple[float, float]],
    total: float,
    x_cop: float,
    y_cop: float,
    half_x: float,
    half_y: float,
) -> dict[str, float] | None:
    """選んだ隅だけで、合計と圧力中心を満たす力を求める。解けなければ None。"""
    count = len(active)
    if count == 4:
        return {
            "top_left": total / 4.0 * (1.0 + x_cop / half_x + y_cop / half_y),
            "top_right": total / 4.0 * (1.0 + x_cop / half_x - y_cop / half_y),
            "bottom_left": total / 4.0 * (1.0 - x_cop / half_x + y_cop / half_y),
            "bottom_right": total / 4.0 * (1.0 - x_cop / half_x - y_cop / half_y),
        }
    if count == 1:
        return {active[0]: total}
    if count == 2:
        name0, name1 = active
        x0, y0 = places[name0]
        x1, y1 = places[name1]
        dx = x1 - x0
        dy = y1 - y0
        length2 = dx * dx + dy * dy
        if length2 < 1e-12:
            return None
        # 中心を2隅の線分へ下ろす。線分の外なら近い隅が全部を受ける。
        along = ((x_cop - x0) * dx + (y_cop - y0) * dy) / length2
        if along <= 0.0:
            return {name0: total, name1: 0.0}
        if along >= 1.0:
            return {name0: 0.0, name1: total}
        return {name0: total * (1.0 - along), name1: total * along}
    rows = []
    for name in active:
        x, y = places[name]
        rows.append((1.0, x, y))
    # 未知数は各隅の力。右辺は合計、x 方向のモーメント、y 方向のモーメント。
    matrix = [
        [rows[0][0], rows[1][0], rows[2][0]],
        [rows[0][1], rows[1][1], rows[2][1]],
        [rows[0][2], rows[1][2], rows[2][2]],
    ]
    solved = _solve3(matrix, [total, total * x_cop, total * y_cop])
    if solved is None:
        return None
    return {active[i]: solved[i] for i in range(3)}


def _solve3(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    """3元連立をガウス消去で解く。行列が潰れていれば None。"""
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) < 1e-12:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        for j in range(col, 4):
            a[col][j] /= scale
        for row in range(3):
            if row == col:
                continue
            factor = a[row][col]
            for j in range(col, 4):
                a[row][j] -= factor * a[col][j]
    return [a[0][3], a[1][3], a[2][3]]


def _to_kg(force_n: float) -> float:
    """ニュートンを DF9-40 の kg 表示にし、応答点未満は 0、満量は 2 kg で止める。"""
    kg = max(0.0, force_n) / GRAVITY_MPS2
    if kg < DEADZONE_KG:
        return 0.0
    if kg > DF9_MAX_KG:
        return DF9_MAX_KG
    return kg


def _check() -> None:
    """分配の代表例。Isaac を起動せずに確認する。"""
    half_x = 0.10
    half_y = 0.05

    center = distribute_newtons([(0.0, 0.0, 30.0)], half_x, half_y)
    for key in CORNER_KEYS:
        assert abs(center[key] - 7.5) < 1e-6, center

    toe = distribute_newtons([(0.05, 0.0, 30.0)], half_x, half_y)
    assert abs(toe["top_left"] - 11.25) < 1e-6, toe
    assert abs(toe["top_right"] - 11.25) < 1e-6, toe
    assert abs(toe["bottom_left"] - 3.75) < 1e-6, toe
    assert abs(toe["bottom_right"] - 3.75) < 1e-6, toe

    # つま先左の真上。引っ張る隅を捨てたあと、その1隅が全部を受ける。
    corner = distribute_newtons([(0.10, 0.05, 30.0)], half_x, half_y)
    assert abs(corner["top_left"] - 30.0) < 1e-6, corner
    assert corner["top_right"] == 0.0
    assert corner["bottom_left"] == 0.0
    assert corner["bottom_right"] == 0.0

    # 30 N は約 3.06 kg。1隅に集まると満量 2 kg で止まる。
    clipped = sample_from_points([(PLATE_HALF_X_M, PLATE_HALF_Y_M, 30.0)], seq=1)
    assert clipped["ok"] is True
    assert clipped["corners"]["top_left"]["force_kg"] == DF9_MAX_KG
    assert clipped["corners"]["top_right"]["force_kg"] == 0.0

    idle = sample_from_points([], seq=2)
    assert idle["ok"] is True
    assert idle["force_kg"] == 0.0

    missing = sample_from_points([(0.0, 0.0, 10.0)], seq=3, ok=False)
    assert missing["ok"] is False
    assert missing["force_kg"] == 0.0
    print("sole_pressure ok")


if __name__ == "__main__":
    _check()
