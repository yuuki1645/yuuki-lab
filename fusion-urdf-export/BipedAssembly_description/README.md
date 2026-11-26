# BipedAssembly — Robot Description

![BipedAssembly](images/robot.png)

## Overview

| Property | Value |
|----------|-------|
| Total mass | 9.498 kg |
| Links | 12 |
| Joints | 11 (10 movable) |
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
    PELVIS
      └─ left_hip_roll [revolute]
        L_HIP [BAKE]
          └─ left_hip_pitch [revolute]
            L_THIGH [BAKE]
              └─ left_knee_pitch [revolute]
                L_SHIN [BAKE]
                  └─ left_ankle_pitch [revolute]
                    L_ANKLE [BAKE]
                      └─ left_ankle_roll [revolute]
                        L_FOOT [BAKE]
      └─ right_hip_roll [revolute]
        R_HIP [BAKE]
          └─ right_hip_pitch [revolute]
            R_THIGH [BAKE]
              └─ right_knee_pitch [revolute]
                R_SHIN [BAKE]
                  └─ right_ankle_pitch [revolute]
                    R_ANKLE [BAKE]
                      └─ right_ankle_roll [revolute]
                        R_FOOT [BAKE]
```

## Link Properties

| Link | Mass (kg) | Material | Collision | Bodies |
|------|-----------|----------|-----------|--------|
| `L_ANKLE` | 0.7362 | material | box | 1 |
| `L_FOOT` | 0.4675 | material | box | 1 |
| `L_HIP` | 0.1098 | material | cylinder | 1 |
| `L_SHIN` | 0.9946 | Lipo | box | 1 |
| `L_THIGH` | 1.5519 | Lipo | box | 1 |
| `PELVIS` | 1.6771 | ABS | box | 1 |
| `R_ANKLE` | 0.7362 | material | box | 1 |
| `R_FOOT` | 0.4675 | material | box | 1 |
| `R_HIP` | 0.1098 | material | cylinder | 1 |
| `R_SHIN` | 0.9946 | Lipo | box | 1 |
| `R_THIGH` | 1.5519 | Lipo | box | 1 |
| `base_link` | 0.1013 | material | box | 1 |

## Joint Properties

| Joint | Type | Parent → Child | Axis | Limits |
|-------|------|---------------|------|--------|
| `biped_fixed_01` | fixed | `base_link` → `PELVIS` | (0,0,1) | — |
| `left_ankle_pitch` | revolute | `L_SHIN` → `L_ANKLE` | (0,0,1) | [-40.0°, 40.0°] |
| `left_ankle_roll` | revolute | `L_ANKLE` → `L_FOOT` | (0,0,1) | [-40.0°, 40.0°] |
| `left_hip_pitch` | revolute | `L_HIP` → `L_THIGH` | (0,0,1) | [-40.0°, 40.0°] |
| `left_hip_roll` | revolute | `PELVIS` → `L_HIP` | (0,0,1) | [-40.0°, 40.0°] |
| `left_knee_pitch` | revolute | `L_THIGH` → `L_SHIN` | (0,0,1) | [-40.0°, 40.0°] |
| `right_ankle_pitch` | revolute | `R_SHIN` → `R_ANKLE` | (0,0,1) | [-40.0°, 40.0°] |
| `right_ankle_roll` | revolute | `R_ANKLE` → `R_FOOT` | (0,0,1) | [-40.0°, 40.0°] |
| `right_hip_pitch` | revolute | `R_HIP` → `R_THIGH` | (0,0,1) | [-40.0°, 40.0°] |
| `right_hip_roll` | revolute | `PELVIS` → `R_HIP` | (0,0,1) | [-40.0°, 40.0°] |
| `right_knee_pitch` | revolute | `R_THIGH` → `R_SHIN` | (0,0,1) | [-40.0°, 40.0°] |

## Assembly Breakdown

### 100PCBA_ASM_13_ASM

- **Links**: 
- **Total mass**: 0.000 kg

### BipedAssembly

- **Links**: base_link, PELVIS
- **Total mass**: 1.778 kg

### DSSERVO_RDS51150_BodyOnly

- **Links**: L_ANKLE, R_ANKLE
- **Total mass**: 1.472 kg

### FEETECH_SM105BL

- **Links**: 
- **Total mass**: 0.000 kg

### LegAssembly

- **Links**: L_FOOT, L_SHIN, L_THIGH, R_FOOT, R_SHIN, R_THIGH
- **Total mass**: 6.028 kg

### LegLinkAssembly

- **Links**: 
- **Total mass**: 0.000 kg

### OUTGEAR_ASM_5_ASM

- **Links**: 
- **Total mass**: 0.000 kg

### RDS51150Assembly

- **Links**: L_HIP, R_HIP
- **Total mass**: 0.220 kg

### RDS51150Assembly_hip

- **Links**: 
- **Total mass**: 0.000 kg

### SM100_BL_ASM_159_ASM

- **Links**: 
- **Total mass**: 0.000 kg

### SM105BLAssembly

- **Links**: 
- **Total mass**: 0.000 kg

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