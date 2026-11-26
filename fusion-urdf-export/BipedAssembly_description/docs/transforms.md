# Transformation Matrices - BipedAssembly

Homogeneous transformation matrices between consecutive frames.
Convention: URDF RPY (XYZ extrinsic / ZYX intrinsic).

## Notation

### Frames

| Index | Link |
|-------|------|
| $L_{0}$ | base_link |
| $L_{1}$ | PELVIS |
| $L_{2}$ | L_HIP |
| $L_{3}$ | R_HIP |
| $L_{4}$ | L_THIGH |
| $L_{5}$ | R_THIGH |
| $L_{6}$ | L_SHIN |
| $L_{7}$ | R_SHIN |
| $L_{8}$ | L_ANKLE |
| $L_{9}$ | R_ANKLE |
| $L_{10}$ | L_FOOT |
| $L_{11}$ | R_FOOT |

### Joint Variables

| Variable | Joint | Type | From | To |
|----------|-------|------|------|----|
| $q_{1}$ | left_hip_roll | revolute (rad) | $L_{1}$ | $L_{2}$ |
| $q_{2}$ | right_hip_roll | revolute (rad) | $L_{1}$ | $L_{3}$ |
| $q_{3}$ | left_hip_pitch | revolute (rad) | $L_{2}$ | $L_{4}$ |
| $q_{4}$ | right_hip_pitch | revolute (rad) | $L_{3}$ | $L_{5}$ |
| $q_{5}$ | left_knee_pitch | revolute (rad) | $L_{4}$ | $L_{6}$ |
| $q_{6}$ | right_knee_pitch | revolute (rad) | $L_{5}$ | $L_{7}$ |
| $q_{7}$ | left_ankle_pitch | revolute (rad) | $L_{6}$ | $L_{8}$ |
| $q_{8}$ | right_ankle_pitch | revolute (rad) | $L_{7}$ | $L_{9}$ |
| $q_{9}$ | left_ankle_roll | revolute (rad) | $L_{8}$ | $L_{10}$ |
| $q_{10}$ | right_ankle_roll | revolute (rad) | $L_{9}$ | $L_{11}$ |

Shorthand: $c_i = \cos(q_i)$, $s_i = \sin(q_i)$

### Kinematic Tree

```
L0: base_link
  +-- [fixed] biped_fixed_01
      L1: PELVIS
        |-- [revolute] left_hip_roll (q1)
        |   L2: L_HIP
        |     +-- [revolute] left_hip_pitch (q3)
        |         L4: L_THIGH
        |           +-- [revolute] left_knee_pitch (q5)
        |               L6: L_SHIN
        |                 +-- [revolute] left_ankle_pitch (q7)
        |                     L8: L_ANKLE
        |                       +-- [revolute] left_ankle_roll (q9)
        |                           L10: L_FOOT
        +-- [revolute] right_hip_roll (q2)
            L3: R_HIP
              +-- [revolute] right_hip_pitch (q4)
                  L5: R_THIGH
                    +-- [revolute] right_knee_pitch (q6)
                        L7: R_SHIN
                          +-- [revolute] right_ankle_pitch (q8)
                              L9: R_ANKLE
                                +-- [revolute] right_ankle_roll (q10)
                                    L11: R_FOOT
```

## Transforms

## biped_fixed_01

$L_{0}$ **base_link** -> $L_{1}$ **PELVIS** (fixed)

- **origin xyz**: (-0.065, 0.015, 0.003) m
- **origin rpy**: (0, 0, -1.570796) rad

### Local Transform

$$
T^{0}_{1} = \begin{bmatrix}
0 & 1 & 0 & -0.065 \\
-1 & 0 & 0 & 0.015 \\
0 & 0 & 1 & 0.003 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## left_hip_roll

$L_{1}$ **PELVIS** -> $L_{2}$ **L_HIP** (revolute)
  Variable: $q_{1}$

- **origin xyz**: (0.035, 0.0593, -0.0625) m
- **origin rpy**: (-1.570796, 0, -3.141593) rad
- **axis**: (0, 0, -1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{1}_{2}(q_{1}) = T_{fixed} \cdot R_{axis}(q_{1})$ where:

$$
T_{fixed} = \begin{bmatrix}
-1 & 0 & 0 & 0.035 \\
0 & 0 & -1 & 0.0593 \\
0 & -1 & 0 & -0.0625 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{1}) = \begin{bmatrix}
c_{1} & s_{1} & 0 & 0 \\
-s_{1} & c_{1} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## right_hip_roll

$L_{1}$ **PELVIS** -> $L_{3}$ **R_HIP** (revolute)
  Variable: $q_{2}$

- **origin xyz**: (0.245, 0.0593, -0.0625) m
- **origin rpy**: (-1.570796, 0, -3.141593) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{1}_{3}(q_{2}) = T_{fixed} \cdot R_{axis}(q_{2})$ where:

$$
T_{fixed} = \begin{bmatrix}
-1 & 0 & 0 & 0.245 \\
0 & 0 & -1 & 0.0593 \\
0 & -1 & 0 & -0.0625 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{2}) = \begin{bmatrix}
c_{2} & -s_{2} & 0 & 0 \\
s_{2} & c_{2} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## left_hip_pitch

$L_{2}$ **L_HIP** -> $L_{4}$ **L_THIGH** (revolute)
  Variable: $q_{3}$

- **origin xyz**: (-0.03075, 0.07, -0.03075) m
- **origin rpy**: (-3.141593, 1.570796, 0) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{2}_{4}(q_{3}) = T_{fixed} \cdot R_{axis}(q_{3})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & 0 & -1 & -0.03075 \\
0 & -1 & 0 & 0.07 \\
-1 & 0 & 0 & -0.03075 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{3}) = \begin{bmatrix}
c_{3} & -s_{3} & 0 & 0 \\
s_{3} & c_{3} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## right_hip_pitch

$L_{3}$ **R_HIP** -> $L_{5}$ **R_THIGH** (revolute)
  Variable: $q_{4}$

- **origin xyz**: (-0.03075, 0.07, -0.03075) m
- **origin rpy**: (-3.141593, 1.570796, 0) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{3}_{5}(q_{4}) = T_{fixed} \cdot R_{axis}(q_{4})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & 0 & -1 & -0.03075 \\
0 & -1 & 0 & 0.07 \\
-1 & 0 & 0 & -0.03075 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{4}) = \begin{bmatrix}
c_{4} & -s_{4} & 0 & 0 \\
s_{4} & c_{4} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## left_knee_pitch

$L_{4}$ **L_THIGH** -> $L_{6}$ **L_SHIN** (revolute)
  Variable: $q_{5}$

- **origin xyz**: (0, -0.31725, -0.0056) m
- **origin rpy**: (0, 0, 0) rad
- **axis**: (0, 0, -1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$$
T^{4}_{6}(q_{5}) = \begin{bmatrix}
c_{5} & s_{5} & 0 & 0 \\
-s_{5} & c_{5} & 0 & -0.31725 \\
0 & 0 & 1 & -0.0056 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## right_knee_pitch

$L_{5}$ **R_THIGH** -> $L_{7}$ **R_SHIN** (revolute)
  Variable: $q_{6}$

- **origin xyz**: (0, -0.31725, -0.0056) m
- **origin rpy**: (0, 0, 0) rad
- **axis**: (0, 0, -1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$$
T^{5}_{7}(q_{6}) = \begin{bmatrix}
c_{6} & s_{6} & 0 & 0 \\
-s_{6} & c_{6} & 0 & -0.31725 \\
0 & 0 & 1 & -0.0056 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## left_ankle_pitch

$L_{6}$ **L_SHIN** -> $L_{8}$ **L_ANKLE** (revolute)
  Variable: $q_{7}$

- **origin xyz**: (0, -0.28975, 0.0001) m
- **origin rpy**: (0, 0, 0) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$$
T^{6}_{8}(q_{7}) = \begin{bmatrix}
c_{7} & -s_{7} & 0 & 0 \\
s_{7} & c_{7} & 0 & -0.28975 \\
0 & 0 & 1 & 0.0001 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## right_ankle_pitch

$L_{7}$ **R_SHIN** -> $L_{9}$ **R_ANKLE** (revolute)
  Variable: $q_{8}$

- **origin xyz**: (0, -0.28975, 0.0001) m
- **origin rpy**: (0, 0, 0) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$$
T^{7}_{9}(q_{8}) = \begin{bmatrix}
c_{8} & -s_{8} & 0 & 0 \\
s_{8} & c_{8} & 0 & -0.28975 \\
0 & 0 & 1 & 0.0001 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## left_ankle_roll

$L_{8}$ **L_ANKLE** -> $L_{10}$ **L_FOOT** (revolute)
  Variable: $q_{9}$

- **origin xyz**: (-0.0322, -0.0915, -0.0255) m
- **origin rpy**: (3.141593, 1.570796, 0) rad
- **axis**: (0, 0, -1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{8}_{10}(q_{9}) = T_{fixed} \cdot R_{axis}(q_{9})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & 0 & -1 & -0.0322 \\
0 & -1 & 0 & -0.0915 \\
-1 & 0 & 0 & -0.0255 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{9}) = \begin{bmatrix}
c_{9} & s_{9} & 0 & 0 \\
-s_{9} & c_{9} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## right_ankle_roll

$L_{9}$ **R_ANKLE** -> $L_{11}$ **R_FOOT** (revolute)
  Variable: $q_{10}$

- **origin xyz**: (-0.0322, -0.0915, -0.0255) m
- **origin rpy**: (3.141593, 1.570796, 0) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{9}_{11}(q_{10}) = T_{fixed} \cdot R_{axis}(q_{10})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & 0 & -1 & -0.0322 \\
0 & -1 & 0 & -0.0915 \\
-1 & 0 & 0 & -0.0255 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{10}) = \begin{bmatrix}
c_{10} & -s_{10} & 0 & 0 \\
s_{10} & c_{10} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## Global Transform Chains

Transform from root $L_0$ to any link, as product of local transforms along the kinematic chain.

$$T^{0}_{2} = T^{0}_{1} \cdot T^{1}_{2}(q_{1})\quad (L_0 \to L_{2}: \text{L_HIP})$$

$$T^{0}_{3} = T^{0}_{1} \cdot T^{1}_{3}(q_{2})\quad (L_0 \to L_{3}: \text{R_HIP})$$

$$T^{0}_{4} = T^{0}_{1} \cdot T^{1}_{2}(q_{1}) \cdot T^{2}_{4}(q_{3})\quad (L_0 \to L_{4}: \text{L_THIGH})$$

$$T^{0}_{5} = T^{0}_{1} \cdot T^{1}_{3}(q_{2}) \cdot T^{3}_{5}(q_{4})\quad (L_0 \to L_{5}: \text{R_THIGH})$$

$$T^{0}_{6} = T^{0}_{1} \cdot T^{1}_{2}(q_{1}) \cdot T^{2}_{4}(q_{3}) \cdot T^{4}_{6}(q_{5})\quad (L_0 \to L_{6}: \text{L_SHIN})$$

$$T^{0}_{7} = T^{0}_{1} \cdot T^{1}_{3}(q_{2}) \cdot T^{3}_{5}(q_{4}) \cdot T^{5}_{7}(q_{6})\quad (L_0 \to L_{7}: \text{R_SHIN})$$

$$T^{0}_{8} = T^{0}_{1} \cdot T^{1}_{2}(q_{1}) \cdot T^{2}_{4}(q_{3}) \cdot T^{4}_{6}(q_{5}) \cdot T^{6}_{8}(q_{7})\quad (L_0 \to L_{8}: \text{L_ANKLE})$$

$$T^{0}_{9} = T^{0}_{1} \cdot T^{1}_{3}(q_{2}) \cdot T^{3}_{5}(q_{4}) \cdot T^{5}_{7}(q_{6}) \cdot T^{7}_{9}(q_{8})\quad (L_0 \to L_{9}: \text{R_ANKLE})$$

$$T^{0}_{10} = T^{0}_{1} \cdot T^{1}_{2}(q_{1}) \cdot T^{2}_{4}(q_{3}) \cdot T^{4}_{6}(q_{5}) \cdot T^{6}_{8}(q_{7}) \cdot T^{8}_{10}(q_{9})\quad (L_0 \to L_{10}: \text{L_FOOT})$$

$$T^{0}_{11} = T^{0}_{1} \cdot T^{1}_{3}(q_{2}) \cdot T^{3}_{5}(q_{4}) \cdot T^{5}_{7}(q_{6}) \cdot T^{7}_{9}(q_{8}) \cdot T^{9}_{11}(q_{10})\quad (L_0 \to L_{11}: \text{R_FOOT})$$

