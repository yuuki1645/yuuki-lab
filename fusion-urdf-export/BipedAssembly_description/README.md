# BipedAssembly — Robot Description

![BipedAssembly](images/robot.png)

## Overview

| Property | Value |
|----------|-------|
| Total mass | 69.230 kg |
| Links | 40 |
| Joints | 39 (10 movable) |
| Assemblies | 11 |
| Root link | `base_link` |

## Table of Contents

- [Kinematic Tree](#kinematic-tree)
- [Link Properties](#link-properties)
- [Joint Properties](#joint-properties)
- [Assembly Breakdown](#assembly-breakdown)
- [Quick Start (ROS 2)](#quick-start-ros-2)
- [Files](#files)

## Kinematic Tree

```
base_link [BAKE]
  └─ biped_fixed_01 [fixed]
    DSSERVO_RDS51150_BodyOnly_rigid_01
      └─ LegAssembly_v28_1__RDS51150Assembly_v14_2__rot_01 [revolute]
        RDS51150Assembly_RDS51150OriginalOutputBracket [BAKE]
          └─ LegAssembly_v28_1__fixed_05 [fixed]
            RDS51150Assembly_hip_RDS51150OriginalOutputBracket
              └─ LegAssembly_v28_1__RDS51150Assembly_hip_v2_1__rot_01 [continuous]
                DSSERVO_RDS51150_BodyOnly_rigid_01_3 [BAKE]
                  └─ LegAssembly_v28_1__fixed_04 [fixed]
                    LegAssembly_RDS51150LinkBracket
                      └─ LegAssembly_v28_1__fixed_03 [fixed]
                        LegLinkAssembly_rigid_01
                          └─ LegAssembly_v28_1___18 [fixed]
                            SM105BLAssembly_SM105BLLinkBracket
                              └─ LegAssembly_v28_1__SM105BLAssembly_v19_1__fixed_01 [fixed]
                                SM100_BL_ASM_159_ASM_rigid_01
                                  └─ LegAssembly_v28_1__SM105BLAssembly_v19_1__rot_01 [revolute]
                                    SM105BLAssembly_SM105BLOutputBracket [BAKE]
                                      └─ LegAssembly_v28_1__fixed_06 [fixed]
                                        LegAssembly_SM105BLLinkBracket
                                          └─ LegAssembly_v28_1__fixed_07 [fixed]
                                            LegLinkAssembly_rigid_01_2
                                              └─ LegAssembly_v28_1__fixed_02 [fixed]
                                                SM105BLAssembly_SM105BLLinkBracket_2
                                                  └─ LegAssembly_v28_1__SM105BLAssembly_v19_2__fixed_01 [fixed]
                                                    SM100_BL_ASM_159_ASM_rigid_01_2
                                                      └─ LegAssembly_v28_1__SM105BLAssembly_v19_2__rot_01 [revolute]
                                                        SM105BLAssembly_SM105BLOutputBracket_2 [BAKE]
                                                          └─ LegAssembly_v28_1__fixed_08 [fixed]
                                                            DSSERVO_RDS51150_BodyOnly_rigid_01_2
                                                              └─ LegAssembly_v28_1__RDS51150Assembly_v14_3__rot_01 [revolute]
                                                                RDS51150Assembly_RDS51150OriginalOutputBracket_2 [BAKE]
                                                                  └─ LegAssembly_v28_1__fixed_09 [fixed]
                                                                    LegAssembly_FootPlate
                                                  └─ LegAssembly_v28_1__fixed_11 [fixed]
                                                    LegAssembly_LiPo3S
                              └─ LegAssembly_v28_1__fixed_10 [fixed]
                                LegAssembly_LiPo3S_2
  └─ biped_fixed_02 [fixed]
    DSSERVO_RDS51150_BodyOnly_rigid_01_4
      └─ LegAssembly_v28_2__RDS51150Assembly_v14_2__rot_01 [revolute]
        RDS51150Assembly_RDS51150OriginalOutputBracket_3 [BAKE]
          └─ LegAssembly_v28_2__fixed_05 [fixed]
            RDS51150Assembly_hip_RDS51150OriginalOutputBracket_2
              └─ LegAssembly_v28_2__RDS51150Assembly_hip_v2_1__rot_01 [continuous]
                DSSERVO_RDS51150_BodyOnly_rigid_01_6 [BAKE]
                  └─ LegAssembly_v28_2__fixed_04 [fixed]
                    LegAssembly_RDS51150LinkBracket_2
                      └─ LegAssembly_v28_2__fixed_03 [fixed]
                        LegLinkAssembly_rigid_01_3
                          └─ LegAssembly_v28_2___18 [fixed]
                            SM105BLAssembly_SM105BLLinkBracket_3
                              └─ LegAssembly_v28_2__SM105BLAssembly_v19_1__fixed_01 [fixed]
                                SM100_BL_ASM_159_ASM_rigid_01_3
                                  └─ LegAssembly_v28_2__SM105BLAssembly_v19_1__rot_01 [revolute]
                                    SM105BLAssembly_SM105BLOutputBracket_3 [BAKE]
                                      └─ LegAssembly_v28_2__fixed_06 [fixed]
                                        LegAssembly_SM105BLLinkBracket_2
                                          └─ LegAssembly_v28_2__fixed_07 [fixed]
                                            LegLinkAssembly_rigid_01_4
                                              └─ LegAssembly_v28_2__fixed_02 [fixed]
                                                SM105BLAssembly_SM105BLLinkBracket_4
                                                  └─ LegAssembly_v28_2__SM105BLAssembly_v19_2__fixed_01 [fixed]
                                                    SM100_BL_ASM_159_ASM_rigid_01_4
                                                      └─ LegAssembly_v28_2__SM105BLAssembly_v19_2__rot_01 [revolute]
                                                        SM105BLAssembly_SM105BLOutputBracket_4 [BAKE]
                                                          └─ LegAssembly_v28_2__fixed_08 [fixed]
                                                            DSSERVO_RDS51150_BodyOnly_rigid_01_5
                                                              └─ LegAssembly_v28_2__RDS51150Assembly_v14_3__rot_01 [revolute]
                                                                RDS51150Assembly_RDS51150OriginalOutputBracket_4 [BAKE]
                                                                  └─ LegAssembly_v28_2__fixed_09 [fixed]
                                                                    LegAssembly_FootPlate_2
                                                  └─ LegAssembly_v28_2__fixed_11 [fixed]
                                                    LegAssembly_LiPo3S_3
                              └─ LegAssembly_v28_2__fixed_10 [fixed]
                                LegAssembly_LiPo3S_4
  └─ biped_fixed_03 [fixed]
    PelvisBasket
```

## Link Properties

| Link | Mass (kg) | Material | Collision | Bodies |
|------|-----------|----------|-----------|--------|
| `DSSERVO_RDS51150_BodyOnly_rigid_01` | 0.6469 | material | box | 1 |
| `DSSERVO_RDS51150_BodyOnly_rigid_01_2` | 0.6469 | material | box | 1 |
| `DSSERVO_RDS51150_BodyOnly_rigid_01_3` | 0.6469 | material | box | 1 |
| `DSSERVO_RDS51150_BodyOnly_rigid_01_4` | 0.6469 | material | box | 1 |
| `DSSERVO_RDS51150_BodyOnly_rigid_01_5` | 0.6469 | material | box | 1 |
| `DSSERVO_RDS51150_BodyOnly_rigid_01_6` | 0.6469 | material | box | 1 |
| `LegAssembly_FootPlate` | 1.1996 | material | box | 1 |
| `LegAssembly_FootPlate_2` | 1.1996 | material | box | 1 |
| `LegAssembly_LiPo3S` | 0.3020 | Lipo | box | 1 |
| `LegAssembly_LiPo3S_2` | 0.3020 | Lipo | box | 1 |
| `LegAssembly_LiPo3S_3` | 0.3020 | Lipo | box | 1 |
| `LegAssembly_LiPo3S_4` | 0.3020 | Lipo | box | 1 |
| `LegAssembly_RDS51150LinkBracket` | 0.1088 | material | box | 1 |
| `LegAssembly_RDS51150LinkBracket_2` | 0.1088 | material | box | 1 |
| `LegAssembly_SM105BLLinkBracket` | 0.1091 | material | box | 1 |
| `LegAssembly_SM105BLLinkBracket_2` | 0.1091 | material | box | 1 |
| `LegLinkAssembly_rigid_01` | 0.3734 | material | cylinder | 1 |
| `LegLinkAssembly_rigid_01_2` | 0.3734 | material | cylinder | 1 |
| `LegLinkAssembly_rigid_01_3` | 0.3734 | material | cylinder | 1 |
| `LegLinkAssembly_rigid_01_4` | 0.3734 | material | cylinder | 1 |
| `PelvisBasket` | 57.3678 | material | box | 1 |
| `RDS51150Assembly_RDS51150OriginalOutputBracket` | 0.0549 | material | box | 1 |
| `RDS51150Assembly_RDS51150OriginalOutputBracket_2` | 0.0549 | material | box | 1 |
| `RDS51150Assembly_RDS51150OriginalOutputBracket_3` | 0.0549 | material | box | 1 |
| `RDS51150Assembly_RDS51150OriginalOutputBracket_4` | 0.0549 | material | box | 1 |
| `RDS51150Assembly_hip_RDS51150OriginalOutputBracket` | 0.0549 | material | box | 1 |
| `RDS51150Assembly_hip_RDS51150OriginalOutputBracket_2` | 0.0549 | material | box | 1 |
| `SM100_BL_ASM_159_ASM_rigid_01` | 0.2567 | material | box | 1 |
| `SM100_BL_ASM_159_ASM_rigid_01_2` | 0.2567 | material | box | 1 |
| `SM100_BL_ASM_159_ASM_rigid_01_3` | 0.2567 | material | box | 1 |
| `SM100_BL_ASM_159_ASM_rigid_01_4` | 0.2567 | material | box | 1 |
| `SM105BLAssembly_SM105BLLinkBracket` | 0.1091 | material | box | 1 |
| `SM105BLAssembly_SM105BLLinkBracket_2` | 0.1091 | material | box | 1 |
| `SM105BLAssembly_SM105BLLinkBracket_3` | 0.1091 | material | box | 1 |
| `SM105BLAssembly_SM105BLLinkBracket_4` | 0.1091 | material | box | 1 |
| `SM105BLAssembly_SM105BLOutputBracket` | 0.0893 | material | box | 1 |
| `SM105BLAssembly_SM105BLOutputBracket_2` | 0.0893 | material | box | 1 |
| `SM105BLAssembly_SM105BLOutputBracket_3` | 0.0893 | material | box | 1 |
| `SM105BLAssembly_SM105BLOutputBracket_4` | 0.0893 | material | box | 1 |
| `base_link` | 0.2944 | material | box | 1 |

## Joint Properties

| Joint | Type | Parent → Child | Axis | Limits |
|-------|------|---------------|------|--------|
| `LegAssembly_v28_1__RDS51150Assembly_hip_v2_1__rot_01` | continuous | `RDS51150Assembly_hip_RDS51150OriginalOutputBracket` → `DSSERVO_RDS51150_BodyOnly_rigid_01_3` | (0,0,1) | — |
| `LegAssembly_v28_1__RDS51150Assembly_v14_2__rot_01` | revolute | `DSSERVO_RDS51150_BodyOnly_rigid_01` → `RDS51150Assembly_RDS51150OriginalOutputBracket` | (0,0,1) | [-40.0°, 40.0°] |
| `LegAssembly_v28_1__RDS51150Assembly_v14_3__rot_01` | revolute | `DSSERVO_RDS51150_BodyOnly_rigid_01_2` → `RDS51150Assembly_RDS51150OriginalOutputBracket_2` | (0,0,1) | [-40.0°, 40.0°] |
| `LegAssembly_v28_1__SM105BLAssembly_v19_1__fixed_01` | fixed | `SM105BLAssembly_SM105BLLinkBracket` → `SM100_BL_ASM_159_ASM_rigid_01` | (0,0,1) | — |
| `LegAssembly_v28_1__SM105BLAssembly_v19_1__rot_01` | revolute | `SM100_BL_ASM_159_ASM_rigid_01` → `SM105BLAssembly_SM105BLOutputBracket` | (0,0,1) | [-40.0°, 40.0°] |
| `LegAssembly_v28_1__SM105BLAssembly_v19_2__fixed_01` | fixed | `SM105BLAssembly_SM105BLLinkBracket_2` → `SM100_BL_ASM_159_ASM_rigid_01_2` | (0,0,1) | — |
| `LegAssembly_v28_1__SM105BLAssembly_v19_2__rot_01` | revolute | `SM100_BL_ASM_159_ASM_rigid_01_2` → `SM105BLAssembly_SM105BLOutputBracket_2` | (0,0,1) | [-40.0°, 40.0°] |
| `LegAssembly_v28_1___18` | fixed | `LegLinkAssembly_rigid_01` → `SM105BLAssembly_SM105BLLinkBracket` | (0,0,1) | — |
| `LegAssembly_v28_1__fixed_02` | fixed | `LegLinkAssembly_rigid_01_2` → `SM105BLAssembly_SM105BLLinkBracket_2` | (0,0,1) | — |
| `LegAssembly_v28_1__fixed_03` | fixed | `LegAssembly_RDS51150LinkBracket` → `LegLinkAssembly_rigid_01` | (0,0,1) | — |
| `LegAssembly_v28_1__fixed_04` | fixed | `DSSERVO_RDS51150_BodyOnly_rigid_01_3` → `LegAssembly_RDS51150LinkBracket` | (0,0,1) | — |
| `LegAssembly_v28_1__fixed_05` | fixed | `RDS51150Assembly_RDS51150OriginalOutputBracket` → `RDS51150Assembly_hip_RDS51150OriginalOutputBracket` | (0,0,1) | — |
| `LegAssembly_v28_1__fixed_06` | fixed | `SM105BLAssembly_SM105BLOutputBracket` → `LegAssembly_SM105BLLinkBracket` | (0,0,1) | — |
| `LegAssembly_v28_1__fixed_07` | fixed | `LegAssembly_SM105BLLinkBracket` → `LegLinkAssembly_rigid_01_2` | (0,0,1) | — |
| `LegAssembly_v28_1__fixed_08` | fixed | `SM105BLAssembly_SM105BLOutputBracket_2` → `DSSERVO_RDS51150_BodyOnly_rigid_01_2` | (0,0,1) | — |
| `LegAssembly_v28_1__fixed_09` | fixed | `RDS51150Assembly_RDS51150OriginalOutputBracket_2` → `LegAssembly_FootPlate` | (0,0,1) | — |
| `LegAssembly_v28_1__fixed_10` | fixed | `SM105BLAssembly_SM105BLLinkBracket` → `LegAssembly_LiPo3S_2` | (0,0,1) | — |
| `LegAssembly_v28_1__fixed_11` | fixed | `SM105BLAssembly_SM105BLLinkBracket_2` → `LegAssembly_LiPo3S` | (0,0,1) | — |
| `LegAssembly_v28_2__RDS51150Assembly_hip_v2_1__rot_01` | continuous | `RDS51150Assembly_hip_RDS51150OriginalOutputBracket_2` → `DSSERVO_RDS51150_BodyOnly_rigid_01_6` | (0,0,1) | — |
| `LegAssembly_v28_2__RDS51150Assembly_v14_2__rot_01` | revolute | `DSSERVO_RDS51150_BodyOnly_rigid_01_4` → `RDS51150Assembly_RDS51150OriginalOutputBracket_3` | (0,0,1) | [-40.0°, 40.0°] |
| `LegAssembly_v28_2__RDS51150Assembly_v14_3__rot_01` | revolute | `DSSERVO_RDS51150_BodyOnly_rigid_01_5` → `RDS51150Assembly_RDS51150OriginalOutputBracket_4` | (0,0,1) | [-40.0°, 40.0°] |
| `LegAssembly_v28_2__SM105BLAssembly_v19_1__fixed_01` | fixed | `SM105BLAssembly_SM105BLLinkBracket_3` → `SM100_BL_ASM_159_ASM_rigid_01_3` | (0,0,1) | — |
| `LegAssembly_v28_2__SM105BLAssembly_v19_1__rot_01` | revolute | `SM100_BL_ASM_159_ASM_rigid_01_3` → `SM105BLAssembly_SM105BLOutputBracket_3` | (0,0,1) | [-40.0°, 40.0°] |
| `LegAssembly_v28_2__SM105BLAssembly_v19_2__fixed_01` | fixed | `SM105BLAssembly_SM105BLLinkBracket_4` → `SM100_BL_ASM_159_ASM_rigid_01_4` | (0,0,1) | — |
| `LegAssembly_v28_2__SM105BLAssembly_v19_2__rot_01` | revolute | `SM100_BL_ASM_159_ASM_rigid_01_4` → `SM105BLAssembly_SM105BLOutputBracket_4` | (0,0,1) | [-40.0°, 40.0°] |
| `LegAssembly_v28_2___18` | fixed | `LegLinkAssembly_rigid_01_3` → `SM105BLAssembly_SM105BLLinkBracket_3` | (0,0,1) | — |
| `LegAssembly_v28_2__fixed_02` | fixed | `LegLinkAssembly_rigid_01_4` → `SM105BLAssembly_SM105BLLinkBracket_4` | (0,0,1) | — |
| `LegAssembly_v28_2__fixed_03` | fixed | `LegAssembly_RDS51150LinkBracket_2` → `LegLinkAssembly_rigid_01_3` | (0,0,1) | — |
| `LegAssembly_v28_2__fixed_04` | fixed | `DSSERVO_RDS51150_BodyOnly_rigid_01_6` → `LegAssembly_RDS51150LinkBracket_2` | (0,0,1) | — |
| `LegAssembly_v28_2__fixed_05` | fixed | `RDS51150Assembly_RDS51150OriginalOutputBracket_3` → `RDS51150Assembly_hip_RDS51150OriginalOutputBracket_2` | (0,0,1) | — |
| `LegAssembly_v28_2__fixed_06` | fixed | `SM105BLAssembly_SM105BLOutputBracket_3` → `LegAssembly_SM105BLLinkBracket_2` | (0,0,1) | — |
| `LegAssembly_v28_2__fixed_07` | fixed | `LegAssembly_SM105BLLinkBracket_2` → `LegLinkAssembly_rigid_01_4` | (0,0,1) | — |
| `LegAssembly_v28_2__fixed_08` | fixed | `SM105BLAssembly_SM105BLOutputBracket_4` → `DSSERVO_RDS51150_BodyOnly_rigid_01_5` | (0,0,1) | — |
| `LegAssembly_v28_2__fixed_09` | fixed | `RDS51150Assembly_RDS51150OriginalOutputBracket_4` → `LegAssembly_FootPlate_2` | (0,0,1) | — |
| `LegAssembly_v28_2__fixed_10` | fixed | `SM105BLAssembly_SM105BLLinkBracket_3` → `LegAssembly_LiPo3S_4` | (0,0,1) | — |
| `LegAssembly_v28_2__fixed_11` | fixed | `SM105BLAssembly_SM105BLLinkBracket_4` → `LegAssembly_LiPo3S_3` | (0,0,1) | — |
| `biped_fixed_01` | fixed | `base_link` → `DSSERVO_RDS51150_BodyOnly_rigid_01` | (0,0,1) | — |
| `biped_fixed_02` | fixed | `base_link` → `DSSERVO_RDS51150_BodyOnly_rigid_01_4` | (0,0,1) | — |
| `biped_fixed_03` | fixed | `base_link` → `PelvisBasket` | (0,0,1) | — |

## Assembly Breakdown

### 100PCBA_ASM_13_ASM

- **Links**: 
- **Total mass**: 0.000 kg

### BipedAssembly

- **Links**: base_link, PelvisBasket
- **Total mass**: 57.662 kg

### DSSERVO_RDS51150_BodyOnly

- **Links**: DSSERVO_RDS51150_BodyOnly_rigid_01_3, DSSERVO_RDS51150_BodyOnly_rigid_01, DSSERVO_RDS51150_BodyOnly_rigid_01_2, DSSERVO_RDS51150_BodyOnly_rigid_01_6, DSSERVO_RDS51150_BodyOnly_rigid_01_4, DSSERVO_RDS51150_BodyOnly_rigid_01_5
- **Total mass**: 3.881 kg

### FEETECH_SM105BL

- **Links**: 
- **Total mass**: 0.000 kg

### LegAssembly

- **Links**: LegAssembly_RDS51150LinkBracket, LegAssembly_SM105BLLinkBracket, LegAssembly_FootPlate, LegAssembly_LiPo3S, LegAssembly_LiPo3S_2, LegAssembly_RDS51150LinkBracket_2, LegAssembly_SM105BLLinkBracket_2, LegAssembly_FootPlate_2, LegAssembly_LiPo3S_3, LegAssembly_LiPo3S_4
- **Total mass**: 4.043 kg

### LegLinkAssembly

- **Links**: LegLinkAssembly_rigid_01, LegLinkAssembly_rigid_01_2, LegLinkAssembly_rigid_01_3, LegLinkAssembly_rigid_01_4
- **Total mass**: 1.494 kg

### OUTGEAR_ASM_5_ASM

- **Links**: 
- **Total mass**: 0.000 kg

### RDS51150Assembly

- **Links**: RDS51150Assembly_RDS51150OriginalOutputBracket, RDS51150Assembly_RDS51150OriginalOutputBracket_2, RDS51150Assembly_RDS51150OriginalOutputBracket_3, RDS51150Assembly_RDS51150OriginalOutputBracket_4
- **Total mass**: 0.220 kg

### RDS51150Assembly_hip

- **Links**: RDS51150Assembly_hip_RDS51150OriginalOutputBracket, RDS51150Assembly_hip_RDS51150OriginalOutputBracket_2
- **Total mass**: 0.110 kg

### SM100_BL_ASM_159_ASM

- **Links**: SM100_BL_ASM_159_ASM_rigid_01, SM100_BL_ASM_159_ASM_rigid_01_2, SM100_BL_ASM_159_ASM_rigid_01_3, SM100_BL_ASM_159_ASM_rigid_01_4
- **Total mass**: 1.027 kg

### SM105BLAssembly

- **Links**: SM105BLAssembly_SM105BLLinkBracket, SM105BLAssembly_SM105BLOutputBracket, SM105BLAssembly_SM105BLLinkBracket_2, SM105BLAssembly_SM105BLOutputBracket_2, SM105BLAssembly_SM105BLLinkBracket_3, SM105BLAssembly_SM105BLOutputBracket_3, SM105BLAssembly_SM105BLLinkBracket_4, SM105BLAssembly_SM105BLOutputBracket_4
- **Total mass**: 0.794 kg

## Quick Start (ROS 2)

```bash
# 1. Copy package to your ROS 2 workspace
cp -r BipedAssembly_description ~/ros2_ws/src/

# 2. Build
cd ~/ros2_ws
colcon build --packages-select BipedAssembly_description
source install/setup.bash

# 3. Visualize in RViz2
ros2 launch BipedAssembly_description display.launch.py

# 4. Validate URDF structure
check_urdf install/BipedAssembly_description/share/BipedAssembly_description/urdf/BipedAssembly.urdf

# 5. Print kinematic tree
urdf_to_graphviz install/BipedAssembly_description/share/BipedAssembly_description/urdf/BipedAssembly.urdf
```

**Joint control**: The launch file includes `joint_state_publisher_gui` —
use the sliders to move revolute/prismatic joints in RViz2.

**Topic inspection**:
```bash
# See published joint states
ros2 topic echo /joint_states

# See robot description parameter
ros2 param get /robot_state_publisher robot_description
```

## Files

| Path | Description |
|------|-------------|
| `urdf/BipedAssembly.urdf.xacro` | Top-level xacro (entry point) |
| `urdf/BipedAssembly.urdf` | Flat URDF (for validation) |
| `urdf/assemblies/` | Per-assembly xacro macros |
| `meshes/` | Visual (OBJ) and collision (STL) meshes |
| `launch/display.launch.py` | Launch robot_state_publisher, RViz, and generated controllers |
| `config/joint_state.yaml` | Joint state publisher config |
| `config/ros2_controllers.yaml` | Generated ros2_control controller manager config |
| `robot_data.yaml` | Supplementary data (beyond URDF) |
| `docs/transforms.md` | Transformation matrices (KaTeX) |

## Customizing

Assemblies tagged `!dummy_` are designed to be swapped out. To replace one:

1. Create your replacement as a xacro macro with the same interface
2. Place it in `urdf/assemblies/`
3. Update the `<xacro:include>` in `urdf/BipedAssembly.urdf.xacro`
4. Update meshes in `meshes/<your_assembly>/`

The xacro prefix system (`${prefix}`) ensures link names stay unique
when multiple instances of the same assembly are used.

---
*Generated by Fusion URDF/XACRO Exporter v3.1.2*