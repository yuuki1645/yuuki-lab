"""カゴと両脚だけの歩行用アーティキュレーション。

形状の正本は `robot_description/yuuki_biped.urdf`。ここにある古い
`yuuki_biped`（バランス棒つき 12 関節）は使わない。USD は直立確認と同じ
`.usd_float` にキャッシュし、カゴは地面へ固定しない。

衝突は URDF の箱をそのまま使う。関節で直接つながった部品だけは PhysX が無視する。
それ以外（左右の脚、足裏と反対のすね、自分のすねと足裏）は当たる。
"""

from __future__ import annotations

from pathlib import Path

from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.sim.converters import UrdfConverterCfg
from isaaclab.sim.spawners.from_files import UrdfFileCfg

from yuuki_isaac_lab.assets.robots.yuuki_legs.model_size import SOLE_BELOW_ORIGIN_M
from yuuki_isaac_lab.tasks.manager_based.biped_walk.mdp.rewards import OPEN_STANCE_ROLL_RAD

# リポジトリ直下の robot_description。yuuki_legs → robots → assets →
# パッケージ → 拡張 → source → isaac-lab → リポジトリ。
_REPO_ROOT = Path(__file__).resolve().parents[7]
_URDF_PATH = _REPO_ROOT / "robot_description" / "yuuki_biped.urdf"
# Hub 再生の .usd_cache（カゴ固定）とは別。
_USD_DIR = _REPO_ROOT / "robot_description" / ".usd_float"

# 1 cm 上から落として、足裏板を床に乗せる。高さ自体は yaml の足裏距離。
SPAWN_CLEARANCE_M = 0.01
# 直立確認で板が床に乗った仮の位置ゲイン。実機の PD ではない。
JOINT_STIFFNESS = 80.0
JOINT_DAMPING = 2.0
# サーボのトルク上限。無限トルクで姿勢を保たせない。
EFFORT_LIMIT_NM = 14.7


def _spawn_yuuki_legs(prim_path: str, cfg: UrdfFileCfg, translation=None, orientation=None, **kwargs):
    """URDF を置き、足までの接触報告を付ける。

    標準の接触報告は最初の剛体（カゴ）で子の探索を止める。足はカゴの子なので、
    ここで足裏まで付けないと ContactSensor はカゴしか見ない。
    自己衝突は変換時に有効のままにする。箱の重なりは URDF 生成側で止めてある。
    spawn_from_urdf は USD を読むので、シミュレータ起動前の設定読み込みでは呼ばない。
    """
    from isaaclab.sim.spawners.from_files.from_files import spawn_from_urdf

    prim = spawn_from_urdf(prim_path, cfg, translation=translation, orientation=orientation, **kwargs)
    _enable_nested_contact_report(prim_path)
    return prim


def _enable_nested_contact_report(prim_path: str) -> None:
    """prim_path に合うロボット以下の、すべての剛体へ接触報告 API を付ける。"""
    from pxr import UsdPhysics

    from isaaclab.sim.utils.prims import safe_set_attribute_on_usd_prim
    from isaaclab.sim.utils.queries import find_matching_prims
    from isaaclab.sim.utils.stage import get_current_stage

    roots = [prim.GetPath().pathString for prim in find_matching_prims(prim_path)]
    stage = get_current_stage()
    for prim in stage.Traverse():
        path = prim.GetPath().pathString
        under_robot = False
        for root in roots:
            if path == root or path.startswith(root + "/"):
                under_robot = True
                break
        if not under_robot or not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        applied = prim.GetAppliedSchemas()
        if "PhysxRigidBodyAPI" not in applied:
            prim.AddAppliedSchema("PhysxRigidBodyAPI")
        # 眠ると接触が欠けるので、しきい値は 0。
        safe_set_attribute_on_usd_prim(prim, "physxRigidBody:sleepThreshold", 0.0, camel_case=False)
        if "PhysxContactReportAPI" not in applied:
            prim.AddAppliedSchema("PhysxContactReportAPI")
        safe_set_attribute_on_usd_prim(prim, "physxContactReport:threshold", 0.0, camel_case=False)


YUUKI_LEGS_CFG = ArticulationCfg(
    prim_path="{ENV_REGEX_NS}/Robot",
    spawn=UrdfFileCfg(
        func=_spawn_yuuki_legs,
        asset_path=str(_URDF_PATH),
        usd_dir=str(_USD_DIR),
        fix_base=False,
        # 足裏の参照リンクを残す。固定関節をまとめると、足裏の球まで親に吸収される。
        merge_fixed_joints=False,
        # URDF に衝突形状がある。見た目から作ると目印の球まで床に当たる。
        collision_from_visuals=False,
        # 足裏の接触を ContactSensor が読めるようにする。
        activate_contact_sensors=True,
        # 関節の隣以外は全部当たる。箱の食い込みは URDF 生成時に止めてある。
        # URDF の中身が変わると変換キャッシュのハッシュも変わるので、古い USD は作り直される。
        self_collision=True,
        joint_drive=UrdfConverterCfg.JointDriveCfg(
            drive_type="force",
            target_type="position",
            gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(
                stiffness=JOINT_STIFFNESS,
                damping=JOINT_DAMPING,
            ),
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, SOLE_BELOW_ORIGIN_M + SPAWN_CLEARANCE_M),
        # ピッチは 0 のまま。ロールだけ、板の内側が約 4 cm 空く角度にする。
        # 正の股ロールは左右とも開く。足首は逆にして、板を床と平行に戻す。
        # 「.*」と併用すると同じ関節が二度一致して初期化に失敗する。
        joint_pos={
            ".*_pitch": 0.0,
            "left_hip_roll": OPEN_STANCE_ROLL_RAD,
            "right_hip_roll": OPEN_STANCE_ROLL_RAD,
            "left_ankle_roll": -OPEN_STANCE_ROLL_RAD,
            "right_ankle_roll": -OPEN_STANCE_ROLL_RAD,
        },
    ),
    actuators={
        "legs": ImplicitActuatorCfg(
            joint_names_expr=[".*"],
            stiffness=JOINT_STIFFNESS,
            damping=JOINT_DAMPING,
            effort_limit_sim=EFFORT_LIMIT_NM,
        ),
    },
)
