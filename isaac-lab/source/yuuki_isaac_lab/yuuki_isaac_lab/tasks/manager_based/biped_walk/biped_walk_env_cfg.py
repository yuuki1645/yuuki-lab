"""カゴと両脚の Manager 歩行タスク。

最初の目標は、ヨーを 0 にしたまま一定速度で前へ歩く環境を用意すること。
歩ける方策はこの設定だけでは出ない。学習を回してから見る。
"""

from __future__ import annotations

import isaaclab.sim as sim_utils
from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab.envs import mdp as isaac_mdp
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.assets import AssetBaseCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.terrains import TerrainImporterCfg
from isaaclab_physx.sensors import ContactSensorCfg
from isaaclab.utils.configclass import configclass

from yuuki_isaac_lab.assets.robots.yuuki_legs import YUUKI_LEGS_CFG

from . import mdp

# 方策の周期。物理 120 Hz を 4 回まとめて、制御は 30 Hz。
_PHYSICS_DT = 1.0 / 120.0
_DECIMATION = 4


@configclass
class BipedWalkSceneCfg(InteractiveSceneCfg):
    """平らな床と、1種類のロボット。"""

    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="plane",
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply",
            restitution_combine_mode="multiply",
            static_friction=1.0,
            dynamic_friction=1.0,
        ),
        visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.32, 0.32, 0.32)),
    )
    robot = YUUKI_LEGS_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")
    # 足リンクだけを見る。床で絞った力と接触位置を、四隅の分配に使う。
    # prim_path の最後の節は名前の正規表現になる。ロボット全体を渡して、
    # 観測側で left_foot / right_foot に絞る。
    contact_forces = ContactSensorCfg(
        prim_path="{ENV_REGEX_NS}/Robot/.*",
        # 平らな床の衝突面。このプリムで絞らないと、圧力中心が取れない。
        filter_prim_paths_expr=["/World/ground/terrain/GroundPlane/CollisionPlane"],
        track_contact_points=True,
        # 接触点を残す上限。足裏は床との接触が数点なので、この数で足りる。
        max_contact_data_count_per_prim=4,
        history_length=0,
    )
    sky_light = AssetBaseCfg(
        prim_path="/World/skyLight",
        spawn=sim_utils.DomeLightCfg(intensity=3000.0, color=(0.8, 0.8, 0.8)),
    )


@configclass
class CommandsCfg:
    """前進は 0.1 m/s で一定、ヨーは 0。横移動は指令に入れない。

    距離の記録だけ SlowWalkVelocityCommand に替える。報酬の計算は変えない。
    """

    base_velocity = isaac_mdp.UniformVelocityCommandCfg(
        asset_name="robot",
        resampling_time_range=(10.0, 10.0),
        rel_standing_envs=0.0,
        heading_command=False,
        debug_vis=False,
        class_type="yuuki_isaac_lab.tasks.manager_based.biped_walk.mdp.forward_command:SlowWalkVelocityCommand",
        ranges=isaac_mdp.UniformVelocityCommandCfg.Ranges(
            lin_vel_x=(mdp.FORWARD_SPEED_MPS, mdp.FORWARD_SPEED_MPS),
            lin_vel_y=(0.0, 0.0),
            ang_vel_z=(0.0, 0.0),
        ),
    )


@configclass
class ActionsCfg:
    """関節目標は直立（0 rad）からの差分。1 アクションは 0.25 rad。"""

    joint_pos = isaac_mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=[".*"],
        scale=0.25,
        use_default_offset=True,
    )


@configclass
class ObservationsCfg:
    """policy が方策、critic が批評家の追加分。"""

    @configclass
    class PolicyCfg(ObsGroup):
        """CoreS3 が作れる量。並びはこの定義順。"""

        joint_pos = ObsTerm(func=isaac_mdp.joint_pos)
        imu_gravity = ObsTerm(func=isaac_mdp.projected_gravity)
        imu_ang_vel = ObsTerm(func=isaac_mdp.base_ang_vel)
        foot_kg = ObsTerm(
            func=mdp.foot_corner_kg,
            params={
                "sensor_cfg": SceneEntityCfg(
                    "contact_forces",
                    body_names=["left_foot", "right_foot"],
                    preserve_order=True,
                ),
                "sole_cfg": SceneEntityCfg(
                    "robot",
                    body_names=["left_sole", "right_sole"],
                    preserve_order=True,
                ),
            },
        )
        phase = ObsTerm(func=mdp.phase_sincos)
        command = ObsTerm(func=mdp.command_forward_and_yaw, params={"command_name": "base_velocity"})
        # 直前の関節目標。実機も、最後に出した角度は知っている。
        last_action = ObsTerm(func=isaac_mdp.last_action)

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = True

    @configclass
    class CriticCfg(ObsGroup):
        """実機には無い状態。方策の入力には足さない。"""

        base_lin_vel = ObsTerm(func=isaac_mdp.base_lin_vel)
        root_height = ObsTerm(func=mdp.root_height, params={"asset_cfg": SceneEntityCfg("robot")})
        joint_vel = ObsTerm(func=isaac_mdp.joint_vel)

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = True

    policy: PolicyCfg = PolicyCfg()
    critic: CriticCfg = CriticCfg()


@configclass
class RewardsCfg:
    """重みは最初の仮説。歩けるかどうかは学習してから判断する。

    feet_apart は、板の内側が約 4 cm 空く間隔を頂点にする。重なった深さは減点。
    初期姿勢の股ロールも、同じ間隔に開いてある。
    """

    upright = RewTerm(func=mdp.upright, weight=1.0)
    # 関数は正味の速度/指令。0.1 m/s を保つと 1、戻すとマイナス。重み 1.5 は毎秒の上限。
    track_forward = RewTerm(
        func=mdp.track_forward_progress,
        weight=1.5,
        params={"command_name": "base_velocity"},
    )
    slide_and_yaw = RewTerm(func=mdp.penalize_slide_and_yaw, weight=-0.5)
    stance = RewTerm(
        func=mdp.stance_contact,
        weight=1.0,
        params={
            "sensor_cfg": SceneEntityCfg(
                "contact_forces",
                body_names=["left_foot", "right_foot"],
                preserve_order=True,
            ),
            "sole_cfg": SceneEntityCfg(
                "robot",
                body_names=["left_sole", "right_sole"],
                preserve_order=True,
            ),
        },
    )
    heel_to_toe = RewTerm(
        func=mdp.heel_to_toe,
        weight=0.5,
        params={
            "sensor_cfg": SceneEntityCfg(
                "contact_forces",
                body_names=["left_foot", "right_foot"],
                preserve_order=True,
            ),
            "sole_cfg": SceneEntityCfg(
                "robot",
                body_names=["left_sole", "right_sole"],
                preserve_order=True,
            ),
        },
    )
    feet_apart = RewTerm(
        func=mdp.feet_apart,
        weight=1.0,
        params={
            # 左、右の順。報酬は左の左右位置から右を引く。
            "asset_cfg": SceneEntityCfg(
                "robot",
                body_names=["left_foot", "right_foot"],
                preserve_order=True,
            )
        },
    )
    swing_knee = RewTerm(
        func=mdp.swing_knee,
        weight=0.3,
        params={
            "asset_cfg": SceneEntityCfg(
                "robot",
                joint_names=["left_knee_pitch", "right_knee_pitch"],
                preserve_order=True,
            )
        },
    )
    action_rate = RewTerm(func=isaac_mdp.action_rate_l2, weight=-0.01)


@configclass
class TerminationsCfg:
    """倒れたら終わり。時間切れは打ち切りで、失敗ではない。"""

    time_out = DoneTerm(func=isaac_mdp.time_out, time_out=True)
    fallen = DoneTerm(
        func=isaac_mdp.root_height_below_minimum,
        params={"minimum_height": 0.35},
    )
    tilted = DoneTerm(
        func=isaac_mdp.bad_orientation,
        params={"limit_angle": 0.7},
    )


@configclass
class EventsCfg:
    """リセットで既定姿勢へ戻す。足サーボは板の上にあるので、衝突は切らない。"""

    reset_scene_to_default = EventTerm(func=isaac_mdp.reset_scene_to_default, mode="reset")


@configclass
class BipedWalkEnvCfg(ManagerBasedRLEnvCfg):
    """YuukiLab-BipedWalk-v0。"""

    scene: BipedWalkSceneCfg = BipedWalkSceneCfg(num_envs=4096, env_spacing=2.5)
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    commands: CommandsCfg = CommandsCfg()
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    events: EventsCfg = EventsCfg()

    def __post_init__(self):
        self.decimation = _DECIMATION
        self.episode_length_s = 10.0
        self.sim.dt = _PHYSICS_DT
        self.sim.render_interval = self.decimation
        self.viewer.eye = (1.8, -1.6, 0.85)
        self.viewer.lookat = (0.0, 0.0, 0.35)


@configclass
class BipedWalkEnvCfg_PLAY(BipedWalkEnvCfg):
    """1体だけ見て再生するための設定。学習の本体は BipedWalkEnvCfg。"""

    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 1
        self.scene.env_spacing = 2.5
