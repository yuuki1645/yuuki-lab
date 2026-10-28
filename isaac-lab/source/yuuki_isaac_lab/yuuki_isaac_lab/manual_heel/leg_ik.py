# Copyright (c) 2022-2026, The Isaac Lab Project Developers.
# SPDX-License-Identifier: BSD-3-Clause

"""robot_description の両脚の逆運動学。

腰（URDF の ``basket``、カゴ底の中心）を原点にした座標系で、足裏板の後ろ端（踵）の位置から
5 関節の角度を求める。股のヨーは無い。バランス棒も胴体関節も無い。

関節の並びは次のとおり。

    hip_roll, hip_pitch, knee_pitch, ankle_pitch, ankle_roll

左のロール軸は +X、右のロール軸は -X。関節角 q の回転は ``Rx(roll_sign * q)`` で、
右は ``roll_sign = -1``。正のピッチと正の膝は、どちらも脚を腰の -X（後ろ）へ折る。

足裏は、関節余裕があるかぎり腰の XY と平行に保つ（足首で股のロールとピッチ合計を打ち消す）。
指定した XY が今の高さでは脚の長さか関節可動域の外なら、XY を優先して高さを一番近い届く値にずらす。
それでも XY 自体が届かないときは失敗を返し、呼び出し側は目標を進めてはいけない。
"""

from __future__ import annotations

import numpy as np

# 股ロール関節から股ピッチ関節まで（腰の下向き）。サーボ 1 段。
_L_HIP = 0.065
# 股ピッチから膝まで。yaml の segment length。
_L_THIGH = 0.226
# 膝から足首ピッチまで。腿と同じ軸間距離。
_L_SHIN = 0.226
# 足首ピッチから足首ロールまで。サーボ 1 段。
_L_ANKLE = 0.065
# 足裏が腰と平行なとき、足首ロール関節から踵までの腰座標オフセット。
# 足リンクから足裏中心は (0.05, 0, -0.058)。板の長さ 0.30 m の後ろ半分が踵。
# 踵 = 足裏中心 + (-0.15, 0, 0) = 足首ロールから (-0.10, 0, -0.058)。
_HEEL_FROM_ANKLE_ROLL = np.array([-0.10, 0.0, -0.058])

# yuuki_biped.yaml の可動域 [rad]。左右で同じ。正の膝は後ろへ折れる。
LEG_LIMITS = np.array(
    [
        [-0.785398, 0.785398],  # hip roll ±45 deg
        [-0.785398, 1.570796],  # hip pitch -45..+90 deg
        [0.000000, 2.094395],  # knee 0..120 deg
        [-0.785398, 0.785398],  # ankle pitch ±45 deg
        [-0.523599, 0.523599],  # ankle roll ±30 deg
    ],
    dtype=float,
)

# 股ロール軸の Y。左が腰の +Y。間隔は yaml の 0.09 m。
Y_HIP_LEFT = 0.09
Y_HIP_RIGHT = -0.09
# ロール軸の符号。左は +X、右は -X。関節角に掛けてから Rx する。
ROLL_SIGN_LEFT = 1.0
ROLL_SIGN_RIGHT = -1.0

# 位置を「届いた」とみなす許容 [m]。これより悪い XY は、その高さを不採用にする。
_POS_TOL = 0.008


def stand_heel(y_hip: float, roll_sign: float = 1.0) -> np.ndarray:
    """全関節 0 のときの踵位置（腰座標系）を返す。"""
    heel, _ = fk_heel(np.zeros(5), y_hip, roll_sign)
    return heel


def fk_heel(q: np.ndarray, y_hip: float, roll_sign: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """関節角から踵位置と足裏の回転を求める。

    Args:
        q: ``[hip_roll, hip_pitch, knee_pitch, ankle_pitch, ankle_roll]`` [rad]。
        y_hip: 股ロール関節の腰座標系 Y [m]。左は正、右は負。
        roll_sign: 左は +1、右は -1。股ロールと足首ロールの軸に掛ける。

    Returns:
        踵位置 [m] と、足裏フレームの回転行列（列が腰座標での足裏の軸）。
        回転が単位行列なら、足裏は腰の XY と平行。
    """
    q1, q2, q3, q4, q5 = (float(v) for v in np.asarray(q, dtype=float).reshape(5))
    # 右脚のロール軸は -X。関節の正方向は、その軸まわりの右ねじ。
    signed_roll = float(roll_sign)
    rotation = np.eye(3)
    point = np.array([0.0, y_hip, 0.0])

    rotation = rotation @ _rx(signed_roll * q1)
    point = point + rotation @ np.array([0.0, 0.0, -_L_HIP])

    rotation = rotation @ _ry(q2)
    point = point + rotation @ np.array([0.0, 0.0, -_L_THIGH])

    rotation = rotation @ _ry(q3)
    point = point + rotation @ np.array([0.0, 0.0, -_L_SHIN])

    rotation = rotation @ _ry(q4)
    point = point + rotation @ np.array([0.0, 0.0, -_L_ANKLE])

    rotation = rotation @ _rx(signed_roll * q5)
    point = point + rotation @ _HEEL_FROM_ANKLE_ROLL
    return point, rotation


def step_heel_target(
    target: np.ndarray,
    delta: np.ndarray,
    y_hip: float,
    q_seed: np.ndarray,
    limits: np.ndarray | None = None,
    roll_sign: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """今の目標に変位を足し、届くときだけ目標と関節角を更新する。

    変位ゼロのフレームでは何もしない。中立のスティックで位置が戻らないのはここ。
    届かない変位は捨てるので、可動域の外へ目標が溜まらない。

    Args:
        target: 現在の踵目標 [m]（腰座標系）。
        delta: このフレームで足したい変位 [m]。
        y_hip: 股関節の Y。
        q_seed: 直前の関節角。数値解の初期値と、失敗したときの保持に使う。
        limits: 関節の上下限。省略時は URDF の可動域。
        roll_sign: 左は +1、右は -1。

    Returns:
        新しい目標、新しい関節角、このフレームで目標を進めたか。
    """
    current = np.asarray(target, dtype=float).reshape(3).copy()
    seed = np.asarray(q_seed, dtype=float).reshape(5).copy()
    step = np.asarray(delta, dtype=float).reshape(3)
    # 入力が無いフレームは解を再計算しない。数値誤差で目標がずれ続けるのを防ぐ。
    if float(np.linalg.norm(step)) < 1.0e-9:
        return current, seed, False

    proposed = current + step
    solved_q, solved_heel, ok = solve_heel(proposed, y_hip, seed, limits, roll_sign)
    if not ok:
        return current, seed, False

    # XY は指令どおり残す。高さだけ、届くためにずらしたとき解の値を記憶する。
    # 解析解は指令高さを誤差なく再現するので、ずらしていないときの微小差では上書きしない。
    height = float(proposed[2])
    if abs(float(solved_heel[2]) - height) > 1.0e-3:
        height = float(solved_heel[2])
    updated = np.array([float(proposed[0]), float(proposed[1]), height], dtype=float)
    # 可動域の端で同じ位置に投影し直しただけなら、目標も関節も動かさない。
    if float(np.linalg.norm(updated - current)) < 2.0e-4:
        return current, seed, False
    return updated, solved_q, True


def solve_heel(
    heel_des: np.ndarray,
    y_hip: float,
    q_seed: np.ndarray,
    limits: np.ndarray | None = None,
    roll_sign: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """腰座標系の踵目標を関節角に落とす。

    まず足裏を腰と平行にした解析解を、指令した高さで試す。
    届かなければ高さを変えて同じ解析解を探し、一番近い高さを採る。
    足裏を平行にできない可動域では、位置を優先した数値解に切り替える。

    Returns:
        関節角、その順運動学での踵位置、XY を許容内で実現できたか。
        失敗時の関節角は ``q_seed``。
    """
    desired = np.asarray(heel_des, dtype=float).reshape(3).copy()
    joint_limits = LEG_LIMITS if limits is None else np.asarray(limits, dtype=float)
    seed = _clip_joints(np.asarray(q_seed, dtype=float).reshape(5), joint_limits)

    exact = _analytical_if_reaches(desired, y_hip, joint_limits, match_height=True, roll_sign=roll_sign)
    if exact is not None:
        return exact

    scanned = _closest_height_analytical(desired, y_hip, joint_limits, roll_sign)
    if scanned is not None:
        return scanned

    numerical = _closest_height_numerical(desired, y_hip, seed, joint_limits, roll_sign)
    if numerical is not None:
        return numerical

    held, _ = fk_heel(seed, y_hip, roll_sign)
    return seed, held, False


def _analytical_if_reaches(
    desired: np.ndarray,
    y_hip: float,
    limits: np.ndarray,
    match_height: bool,
    roll_sign: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, bool] | None:
    """足裏平行の解析解が、許容内で目標に届くときだけ返す。"""
    q = _analytical_flat_sole(desired, y_hip, roll_sign)
    if q is None or not _within_limits(q, limits):
        return None
    q = _clip_joints(q, limits)
    heel, rotation = fk_heel(q, y_hip, roll_sign)
    if float(np.linalg.norm(heel[:2] - desired[:2])) > _POS_TOL:
        return None
    if match_height and abs(float(heel[2] - desired[2])) > _POS_TOL:
        return None
    # 足裏が明らかに傾いていたら、この解析解は前提を外している。
    if float(np.linalg.norm(_sole_tilt(rotation))) > 0.05:
        return None
    return q, heel, True


def _closest_height_analytical(
    desired: np.ndarray,
    y_hip: float,
    limits: np.ndarray,
    roll_sign: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, bool] | None:
    """同じ XY で、指令高さに一番近い届く高さを解析解から選ぶ。

    粗い格子で届く高さを見つけたあと、指令高さとの間を二分する。
    格子のままだと、伸び切った脚をさらに下げようとしたときに足が数ミリ持ち上がる。
    """

    def reaches(height: float) -> tuple[np.ndarray, np.ndarray, bool] | None:
        trial = desired.copy()
        trial[2] = height
        return _analytical_if_reaches(trial, y_hip, limits, match_height=True, roll_sign=roll_sign)

    return _project_height(float(desired[2]), reaches)


def _closest_height_numerical(
    desired: np.ndarray,
    y_hip: float,
    seed: np.ndarray,
    limits: np.ndarray,
    roll_sign: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, bool] | None:
    """足裏の平行を緩めた数値解を、直前姿勢から 1 回だけ求める。

    脚の長さで届かないケースは解析解の高さ探索が先に処理する。
    ここは足首の可動域で足裏を平行にできないとき用なので、高さの総当たりはしない。
    高さも位置も指令どおりに届かなければ、高さの重みを下げてもう一度だけ解く。
    """
    seed_heel, _ = fk_heel(seed, y_hip, roll_sign)
    if float(np.linalg.norm(seed_heel - desired)) < 0.05:
        start = seed
    else:
        free = _analytical_flat_sole(desired, y_hip, roll_sign)
        start = seed if free is None else _clip_joints(free, limits)

    q = _ik_numerical(desired, y_hip, start, limits, z_weight=1.0, iters=10, roll_sign=roll_sign)
    heel, _ = fk_heel(q, y_hip, roll_sign)
    xy_err = float(np.linalg.norm(heel[:2] - desired[:2]))
    z_err = abs(float(heel[2]) - float(desired[2]))
    if xy_err <= _POS_TOL * 1.5 and z_err <= _POS_TOL * 1.5:
        return q, heel, True
    if xy_err <= _POS_TOL * 1.5:
        return q, heel, True

    # 高さを固定したままだと XY が犠牲になるので、高さだけ緩める。
    q = _ik_numerical(desired, y_hip, q, limits, z_weight=0.15, iters=10, roll_sign=roll_sign)
    heel, _ = fk_heel(q, y_hip, roll_sign)
    if float(np.linalg.norm(heel[:2] - desired[:2])) > _POS_TOL * 1.5:
        return None
    return q, heel, True


def _analytical_flat_sole(heel: np.ndarray, y_hip: float, roll_sign: float = 1.0) -> np.ndarray | None:
    """足裏を腰と平行に保ったときの解析解。可動域は見ない。

    足裏平行の条件は ``ankle_roll = -hip_roll`` かつ ``ankle_pitch = -(hip_pitch + knee)``。
    左右のロール軸が同じ符号で逆向きなので、足首ロールを股ロールの逆にすれば足裏は平行に戻る。
    このとき足首から踵までのベクトルは腰座標で一定なので、股と膝の 3 関節で位置が決まる。
    膝は後ろへ折れる枝（``knee >= 0``）だけを返す。
    """
    # 足首ロール関節の目標位置。足裏平行なら踵から一定の引き戻し。
    ankle_roll_point = np.asarray(heel, dtype=float).reshape(3) - _HEEL_FROM_ANKLE_ROLL
    lateral = float(ankle_roll_point[1] - y_hip)
    vertical = float(ankle_roll_point[2])
    radius = float(np.hypot(lateral, vertical))
    # 股の下のリンク長より近い点は、足裏を平行にしたままでは届かない。
    if radius < _L_HIP + _L_ANKLE + 1.0e-6:
        return None
    # +X まわりの回転角。radius * sin(a) = lateral, radius * cos(a) = -vertical。
    # 右脚は軸が -X なので、同じ幾何の角を符号反転して関節角にする。
    about_plus_x = float(np.arctan2(lateral, -vertical))
    hip_roll = float(roll_sign) * about_plus_x
    # 股ピッチ・膝が動かす矢状面内の残り長さ。正が腰の下向き。
    radial_after_hip = radius - _L_ANKLE - _L_HIP
    # Ry の右ねじでは、正のピッチが足を腰の -X（後ろ）へ振る。
    # 2 リンク式は「正の角が +X」で立てているので、前後はここで反転する。
    sagittal_x = -float(ankle_roll_point[0])
    reach_sq = sagittal_x * sagittal_x + radial_after_hip * radial_after_hip
    cosine_knee = (reach_sq - _L_THIGH * _L_THIGH - _L_SHIN * _L_SHIN) / (2.0 * _L_THIGH * _L_SHIN)
    if cosine_knee < -1.0 - 1.0e-6 or cosine_knee > 1.0 + 1.0e-6:
        return None
    cosine_knee = float(np.clip(cosine_knee, -1.0, 1.0))
    # 正の膝角が、この機体の「後ろへ折れる」枝。sin を正にしてその枝だけを採る。
    sine_knee = float(np.sqrt(max(0.0, 1.0 - cosine_knee * cosine_knee)))
    knee = float(np.arctan2(sine_knee, cosine_knee))
    hip_pitch = float(
        np.arctan2(sagittal_x, radial_after_hip)
        - np.arctan2(sine_knee * _L_SHIN, _L_THIGH + cosine_knee * _L_SHIN)
    )
    ankle_pitch = -(hip_pitch + knee)
    ankle_roll = -hip_roll
    return np.array([hip_roll, hip_pitch, knee, ankle_pitch, ankle_roll], dtype=float)


def _ik_numerical(
    desired: np.ndarray,
    y_hip: float,
    q_init: np.ndarray,
    limits: np.ndarray,
    z_weight: float = 1.0,
    iters: int = 25,
    roll_sign: float = 1.0,
) -> np.ndarray:
    """位置を主、足裏の傾きを従にした減衰最小二乗の反復。"""
    q = _clip_joints(q_init, limits)
    lo = limits[:, 0]
    hi = limits[:, 1]
    # 傾きの重みは小さい。位置が可動域と衝突したら、足裏が傾いてでも踵を優先する。
    weight = np.diag([1.0, 1.0, z_weight, 0.05, 0.05])
    damping = 0.08
    best_q = q.copy()
    best_err = float("inf")
    stalled = 0
    for _ in range(iters):
        heel, rotation = fk_heel(q, y_hip, roll_sign)
        tilt = _sole_tilt(rotation)
        error = np.array(
            [
                desired[0] - heel[0],
                desired[1] - heel[1],
                desired[2] - heel[2],
                -tilt[0],
                -tilt[1],
            ],
            dtype=float,
        )
        pos_err = float(np.linalg.norm(error[:3]))
        weighted_err = _weighted_position_error(error[:3], z_weight)
        if pos_err < best_err:
            best_err = pos_err
            best_q = q.copy()
        if pos_err < 1.0e-4 and float(np.linalg.norm(tilt)) < 0.02:
            break
        jacobian = _finite_difference_jacobian(q, y_hip, desired, error, lo, hi, roll_sign)
        system = jacobian.T @ weight @ jacobian + (damping * damping) * np.eye(5)
        # J は残差（目標 - 現在）の微分。残差を消す方向は -J^T r。
        rhs = -jacobian.T @ weight @ error
        try:
            step = np.linalg.solve(system, rhs)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(system, rhs, rcond=None)[0]
        step = np.clip(step, -0.35, 0.35)
        # 誤差が増えるステップは捨て、縮めたステップ幅だけを採用する。
        improved = q
        improved_err = weighted_err
        for scale in (1.0, 0.5, 0.25):
            trial = _clip_joints(q + scale * step, limits)
            trial_heel, _ = fk_heel(trial, y_hip, roll_sign)
            trial_err = _weighted_position_error(desired - trial_heel, z_weight)
            if trial_err + 1.0e-9 < improved_err:
                improved = trial
                improved_err = trial_err
        if np.allclose(improved, q):
            stalled += 1
            if stalled >= 2:
                break
        else:
            stalled = 0
        q = improved
    return best_q


def _weighted_position_error(delta: np.ndarray, z_weight: float) -> float:
    """XY を主、高さを ``z_weight`` で見た位置誤差。"""
    return float(np.hypot(delta[0], delta[1]) + z_weight * abs(delta[2]))


def _finite_difference_jacobian(
    q: np.ndarray,
    y_hip: float,
    desired: np.ndarray,
    error: np.ndarray,
    lo: np.ndarray,
    hi: np.ndarray,
    roll_sign: float = 1.0,
) -> np.ndarray:
    """誤差ベクトルの関節微分。可動域で止まった関節の列は 0。"""
    jacobian = np.zeros((5, 5), dtype=float)
    eps = 1.0e-4
    for index in range(5):
        nudged = q.copy()
        nudged[index] = float(np.clip(q[index] + eps, lo[index], hi[index]))
        delta = float(nudged[index] - q[index])
        if abs(delta) < 1.0e-8:
            continue
        heel, rotation = fk_heel(nudged, y_hip, roll_sign)
        tilt = _sole_tilt(rotation)
        nudged_error = np.array(
            [
                desired[0] - heel[0],
                desired[1] - heel[1],
                desired[2] - heel[2],
                -tilt[0],
                -tilt[1],
            ],
            dtype=float,
        )
        jacobian[:, index] = (nudged_error - error) / delta
    return jacobian


def _project_height(target_z: float, reaches, coarse_step: int = 1):
    """届く高さのうち、``target_z`` に一番近い解を返す。

    ``reaches(z)`` は届くとき解のタプル、届かないとき None。
    粗い格子で見つけた点と指令高さの間を二分し、境界まで寄せる。
    """
    candidates = _height_candidates(target_z)[::coarse_step]
    seed = None
    for height in candidates:
        seed = reaches(float(height))
        if seed is not None:
            near = float(height)
            break
    if seed is None:
        return None
    far = target_z
    for _ in range(20):
        mid = 0.5 * (near + far)
        hit = reaches(mid)
        if hit is not None:
            near = mid
            seed = hit
        else:
            far = mid
    return seed


def _height_candidates(target_z: float) -> np.ndarray:
    """腰座標系で踵が届きうる高さを、指令高さに近い順で返す。"""
    # 全関節 0 の踵は約 -0.64 m。折り畳みと前方への振りで、これより上にも届く。
    coarse = np.linspace(-0.80, 0.20, 51)
    order = np.argsort(np.abs(coarse - target_z))
    return coarse[order]


def _sole_tilt(rotation: np.ndarray) -> np.ndarray:
    """足裏回転のロールとピッチ [rad]。ヨーは股に軸が無いので見ない。"""
    # 微小回転ベクトルの x, y 成分。単位行列なら両方 0。
    roll = 0.5 * (rotation[2, 1] - rotation[1, 2])
    pitch = 0.5 * (rotation[0, 2] - rotation[2, 0])
    return np.array([roll, pitch], dtype=float)


def _within_limits(q: np.ndarray, limits: np.ndarray, eps: float = 1.0e-5) -> bool:
    return bool(np.all(q >= limits[:, 0] - eps) and np.all(q <= limits[:, 1] + eps))


def _clip_joints(q: np.ndarray, limits: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(q, dtype=float).reshape(5), limits[:, 0], limits[:, 1])


def _rx(angle: float) -> np.ndarray:
    c, s = float(np.cos(angle)), float(np.sin(angle))
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]], dtype=float)


def _ry(angle: float) -> np.ndarray:
    c, s = float(np.cos(angle)), float(np.sin(angle))
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]], dtype=float)


def run_self_check() -> None:
    """解析解の往復と、伸び切った脚の高さ緩和を確認する。"""
    # 全関節 0 の踵。板の後ろ端は、足首の真下より 0.10 m 後ろ、足裏と同じ高さ。
    heel, rotation = fk_heel(np.zeros(5), Y_HIP_LEFT, ROLL_SIGN_LEFT)
    expected = np.array([-0.10, Y_HIP_LEFT, -(_L_HIP + _L_THIGH + _L_SHIN + _L_ANKLE) - 0.058])
    if np.linalg.norm(heel - expected) > 1.0e-9:
        raise AssertionError(f"stand FK mismatch: {heel} expected {expected}")
    if np.linalg.norm(heel - stand_heel(Y_HIP_LEFT, ROLL_SIGN_LEFT)) > 1.0e-9:
        raise AssertionError(f"stand helper mismatch: {heel}")
    if np.linalg.norm(rotation - np.eye(3)) > 1.0e-9:
        raise AssertionError("stand sole is not aligned with the waist")

    # 正の股ロールは左右とも脚を開く。右は軸が -X なので、同じ正の角が -Y へ出る。
    left_open, _ = fk_heel(np.array([0.30, 0.0, 0.0, 0.0, -0.30]), Y_HIP_LEFT, ROLL_SIGN_LEFT)
    right_open, right_rot = fk_heel(np.array([0.30, 0.0, 0.0, 0.0, -0.30]), Y_HIP_RIGHT, ROLL_SIGN_RIGHT)
    if left_open[1] <= Y_HIP_LEFT or right_open[1] >= Y_HIP_RIGHT:
        raise AssertionError(f"roll sign does not open both legs: L={left_open} R={right_open}")
    if np.linalg.norm(right_rot - np.eye(3)) > 1.0e-6:
        raise AssertionError("right flat sole did not cancel the mirrored roll")
    # 正の膝は後ろ（-X）へ折れる。
    bent, _ = fk_heel(np.array([0.0, 0.0, 0.40, -0.40, 0.0]), Y_HIP_LEFT, ROLL_SIGN_LEFT)
    if bent[0] >= heel[0]:
        raise AssertionError(f"positive knee did not swing backward: {bent[0]} vs {heel[0]}")

    rng = np.random.default_rng(0)
    checked = 0
    for y_hip, roll_sign in ((Y_HIP_LEFT, ROLL_SIGN_LEFT), (Y_HIP_RIGHT, ROLL_SIGN_RIGHT)):
        for _ in range(80):
            # 足首の可動域に収まる足裏平行の姿勢だけを往復させる。
            q1 = float(rng.uniform(-0.40, 0.40))
            q2 = float(rng.uniform(-0.50, 0.70))
            q3 = float(rng.uniform(0.0, 0.90))
            q = np.array([q1, q2, q3, -(q2 + q3), -q1], dtype=float)
            if not _within_limits(q, LEG_LIMITS):
                continue
            target, target_rot = fk_heel(q, y_hip, roll_sign)
            if np.linalg.norm(_sole_tilt(target_rot)) > 1.0e-6:
                raise AssertionError("flat-sole sample is tilted")
            solved_q, solved_heel, ok = solve_heel(target, y_hip, np.zeros(5), roll_sign=roll_sign)
            if not ok or np.linalg.norm(solved_heel - target) > 1.0e-4:
                raise AssertionError(f"roundtrip failed y={y_hip} q={q} got={solved_heel} ok={ok}")
            # 関節そのものも戻る。膝の枝を一つにしているので、別解へ飛ばない。
            if np.linalg.norm(solved_q - q) > 1.0e-3:
                raise AssertionError(f"joint roundtrip failed {q} -> {solved_q}")
            checked += 1
    if checked < 40:
        raise AssertionError(f"too few roundtrip samples: {checked}")

    # 伸び切った状態から水平に動かすと、同じ高さでは届かない。高さは上がる。
    straight = stand_heel(Y_HIP_LEFT, ROLL_SIGN_LEFT)
    moved, q_moved, advanced = step_heel_target(
        straight,
        np.array([0.06, 0.0, 0.0]),
        Y_HIP_LEFT,
        np.zeros(5),
        roll_sign=ROLL_SIGN_LEFT,
    )
    if not advanced:
        raise AssertionError("forward step from full extension was rejected")
    if abs(moved[0] - (straight[0] + 0.06)) > 1.0e-6:
        raise AssertionError(f"XY was not preserved: {moved}")
    if moved[2] <= straight[2] + 1.0e-3:
        raise AssertionError(f"height was not relaxed upward: {straight[2]} -> {moved[2]}")

    # 中立（変位ゼロ）では、緩和したあとの位置を保つ。
    held, q_held, advanced_again = step_heel_target(
        moved, np.zeros(3), Y_HIP_LEFT, q_moved, roll_sign=ROLL_SIGN_LEFT
    )
    if advanced_again or np.linalg.norm(held - moved) > 0.0 or np.linalg.norm(q_held - q_moved) > 0.0:
        raise AssertionError("neutral input moved the stored heel")

    # さらに床側へは伸びしろが無いので、目標を溜めない。
    down = stand_heel(Y_HIP_LEFT, ROLL_SIGN_LEFT)
    stayed, _, advanced_down = step_heel_target(
        down, np.array([0.0, 0.0, -0.03]), Y_HIP_LEFT, np.zeros(5), roll_sign=ROLL_SIGN_LEFT
    )
    if advanced_down or np.linalg.norm(stayed - down) > 0.0:
        raise AssertionError("unreachable downward step was stored")

    # 数値解は、直前の姿勢から数ミリ動かす使い方をする。伸び切りの特異点は解析解が担当する。
    q_near = np.array([0.0, -0.35, 0.45, -0.10, 0.0], dtype=float)
    heel_near, _ = fk_heel(q_near, Y_HIP_LEFT, ROLL_SIGN_LEFT)
    nudged = heel_near + np.array([0.01, 0.012, -0.008])
    q_num = _ik_numerical(nudged, Y_HIP_LEFT, q_near, LEG_LIMITS, iters=10, roll_sign=ROLL_SIGN_LEFT)
    heel_num, _ = fk_heel(q_num, Y_HIP_LEFT, ROLL_SIGN_LEFT)
    if np.linalg.norm(heel_num - nudged) > 0.008:
        raise AssertionError(f"numerical IK missed {nudged} got {heel_num}")

    # 横へ小刻みに積んでも、届かない分は目標に残らない。
    lateral = stand_heel(Y_HIP_LEFT, ROLL_SIGN_LEFT)
    q_lat = np.zeros(5)
    for _ in range(40):
        lateral, q_lat, _ = step_heel_target(
            lateral, np.array([0.0, 0.01, 0.0]), Y_HIP_LEFT, q_lat, roll_sign=ROLL_SIGN_LEFT
        )
    if lateral[1] > 0.55:
        raise AssertionError(f"lateral target wound up: {lateral}")
    heel_lat, _ = fk_heel(q_lat, Y_HIP_LEFT, ROLL_SIGN_LEFT)
    if np.linalg.norm(heel_lat[:2] - lateral[:2]) > 0.02:
        raise AssertionError(f"stored target left the foot: target={lateral} heel={heel_lat}")

    print(f"leg_ik self-check: OK ({checked} roundtrips)")


if __name__ == "__main__":
    run_self_check()
