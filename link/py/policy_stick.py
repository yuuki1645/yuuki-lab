"""実機画面の前進スティック。腰へ渡す前の速度だけを扱う。

奥への倒し方は画面側で、シミュの左スティックに合わせる。
ここは、届いた数値を 0〜0.2 m/s に収め、ログに残す境界を決める。
0.02 m/s は腰の kVxStand。これ以下では前進 0 の包絡が残る。
"""

from __future__ import annotations

# 腰 walk_policy.cpp の kVxStand。超えると包絡の停止と頭打ちが外れる。
POLICY_VX_STAND_MPS = 0.02
# 腰 policyRequest と cmd_policy と同じ上限。
POLICY_VX_MAX_MPS = 0.2


def clamp_policy_vx(value: object) -> float | None:
    """数値なら 0〜0.2 m/s。真偽値や文字は None で、送らない。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    vx = float(value)
    # NaN は比較が全部偽になるので、ここで落とす。
    if vx != vx:
        return None
    if vx < 0.0:
        return 0.0
    if vx > POLICY_VX_MAX_MPS:
        return POLICY_VX_MAX_MPS
    return vx


def policy_stick_note(prev_mps: float, vx_mps: float) -> str | None:
    """包絡の境界をまたいだときと、中央へ戻ったときだけ文言を返す。

    指の移動ごとにノートを出すと、イベントが前進のログで埋まる。
    """
    if vx_mps <= 1.0e-4 and prev_mps > 1.0e-4:
        return "スティック  中央  vx=0"
    prev_out = prev_mps > POLICY_VX_STAND_MPS
    now_out = vx_mps > POLICY_VX_STAND_MPS
    if now_out and not prev_out:
        return f"スティック  vx={vx_mps:.2f}  包絡は外れています"
    if prev_out and not now_out:
        return f"スティック  vx={vx_mps:.2f}  包絡は戻っています"
    return None
