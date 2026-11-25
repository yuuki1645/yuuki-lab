# Transformation Matrices - BipedAssembly

Homogeneous transformation matrices between consecutive frames.
Convention: URDF RPY (XYZ extrinsic / ZYX intrinsic).

## Notation

### Frames

| Index | Link |
|-------|------|
| $L_{0}$ | base_link |
| $L_{1}$ | DSSERVO_RDS51150_BodyOnly_rigid_01 |
| $L_{2}$ | DSSERVO_RDS51150_BodyOnly_rigid_01_4 |
| $L_{3}$ | PelvisBasket |
| $L_{4}$ | RDS51150Assembly_RDS51150OriginalOutputBracket |
| $L_{5}$ | RDS51150Assembly_RDS51150OriginalOutputBracket_3 |
| $L_{6}$ | RDS51150Assembly_hip_RDS51150OriginalOutputBracket |
| $L_{7}$ | RDS51150Assembly_hip_RDS51150OriginalOutputBracket_2 |
| $L_{8}$ | DSSERVO_RDS51150_BodyOnly_rigid_01_3 |
| $L_{9}$ | DSSERVO_RDS51150_BodyOnly_rigid_01_6 |
| $L_{10}$ | LegAssembly_RDS51150LinkBracket |
| $L_{11}$ | LegAssembly_RDS51150LinkBracket_2 |
| $L_{12}$ | LegLinkAssembly_rigid_01 |
| $L_{13}$ | LegLinkAssembly_rigid_01_3 |
| $L_{14}$ | SM105BLAssembly_SM105BLLinkBracket |
| $L_{15}$ | SM105BLAssembly_SM105BLLinkBracket_3 |
| $L_{16}$ | SM100_BL_ASM_159_ASM_rigid_01 |
| $L_{17}$ | LegAssembly_LiPo3S_2 |
| $L_{18}$ | SM100_BL_ASM_159_ASM_rigid_01_3 |
| $L_{19}$ | LegAssembly_LiPo3S_4 |
| $L_{20}$ | SM105BLAssembly_SM105BLOutputBracket |
| $L_{21}$ | SM105BLAssembly_SM105BLOutputBracket_3 |
| $L_{22}$ | LegAssembly_SM105BLLinkBracket |
| $L_{23}$ | LegAssembly_SM105BLLinkBracket_2 |
| $L_{24}$ | LegLinkAssembly_rigid_01_2 |
| $L_{25}$ | LegLinkAssembly_rigid_01_4 |
| $L_{26}$ | SM105BLAssembly_SM105BLLinkBracket_2 |
| $L_{27}$ | SM105BLAssembly_SM105BLLinkBracket_4 |
| $L_{28}$ | SM100_BL_ASM_159_ASM_rigid_01_2 |
| $L_{29}$ | LegAssembly_LiPo3S |
| $L_{30}$ | SM100_BL_ASM_159_ASM_rigid_01_4 |
| $L_{31}$ | LegAssembly_LiPo3S_3 |
| $L_{32}$ | SM105BLAssembly_SM105BLOutputBracket_2 |
| $L_{33}$ | SM105BLAssembly_SM105BLOutputBracket_4 |
| $L_{34}$ | DSSERVO_RDS51150_BodyOnly_rigid_01_2 |
| $L_{35}$ | DSSERVO_RDS51150_BodyOnly_rigid_01_5 |
| $L_{36}$ | RDS51150Assembly_RDS51150OriginalOutputBracket_2 |
| $L_{37}$ | RDS51150Assembly_RDS51150OriginalOutputBracket_4 |
| $L_{38}$ | LegAssembly_FootPlate |
| $L_{39}$ | LegAssembly_FootPlate_2 |

### Joint Variables

| Variable | Joint | Type | From | To |
|----------|-------|------|------|----|
| $q_{1}$ | LegAssembly_v28_1__RDS51150Assembly_v14_2__rot_01 | revolute (rad) | $L_{1}$ | $L_{4}$ |
| $q_{2}$ | LegAssembly_v28_2__RDS51150Assembly_v14_2__rot_01 | revolute (rad) | $L_{2}$ | $L_{5}$ |
| $q_{3}$ | LegAssembly_v28_1__RDS51150Assembly_hip_v2_1__rot_01 | continuous (rad) | $L_{6}$ | $L_{8}$ |
| $q_{4}$ | LegAssembly_v28_2__RDS51150Assembly_hip_v2_1__rot_01 | continuous (rad) | $L_{7}$ | $L_{9}$ |
| $q_{5}$ | LegAssembly_v28_1__SM105BLAssembly_v19_1__rot_01 | revolute (rad) | $L_{16}$ | $L_{20}$ |
| $q_{6}$ | LegAssembly_v28_2__SM105BLAssembly_v19_1__rot_01 | revolute (rad) | $L_{18}$ | $L_{21}$ |
| $q_{7}$ | LegAssembly_v28_1__SM105BLAssembly_v19_2__rot_01 | revolute (rad) | $L_{28}$ | $L_{32}$ |
| $q_{8}$ | LegAssembly_v28_2__SM105BLAssembly_v19_2__rot_01 | revolute (rad) | $L_{30}$ | $L_{33}$ |
| $q_{9}$ | LegAssembly_v28_1__RDS51150Assembly_v14_3__rot_01 | revolute (rad) | $L_{34}$ | $L_{36}$ |
| $q_{10}$ | LegAssembly_v28_2__RDS51150Assembly_v14_3__rot_01 | revolute (rad) | $L_{35}$ | $L_{37}$ |

Shorthand: $c_i = \cos(q_i)$, $s_i = \sin(q_i)$

### Kinematic Tree

```
L0: base_link
  |-- [fixed] biped_fixed_01
  |   L1: DSSERVO_RDS51150_BodyOnly_rigid_01
  |     +-- [revolute] LegAssembly_v28_1__RDS51150Assembly_v14_2__rot_01 (q1)
  |         L4: RDS51150Assembly_RDS51150OriginalOutputBracket
  |           +-- [fixed] LegAssembly_v28_1__fixed_05
  |               L6: RDS51150Assembly_hip_RDS51150OriginalOutputBracket
  |                 +-- [continuous] LegAssembly_v28_1__RDS51150Assembly_hip_v2_1__rot_01 (q3)
  |                     L8: DSSERVO_RDS51150_BodyOnly_rigid_01_3
  |                       +-- [fixed] LegAssembly_v28_1__fixed_04
  |                           L10: LegAssembly_RDS51150LinkBracket
  |                             +-- [fixed] LegAssembly_v28_1__fixed_03
  |                                 L12: LegLinkAssembly_rigid_01
  |                                   +-- [fixed] LegAssembly_v28_1___18
  |                                       L14: SM105BLAssembly_SM105BLLinkBracket
  |                                         |-- [fixed] LegAssembly_v28_1__SM105BLAssembly_v19_1__fixed_01
  |                                         |   L16: SM100_BL_ASM_159_ASM_rigid_01
  |                                         |     +-- [revolute] LegAssembly_v28_1__SM105BLAssembly_v19_1__rot_01 (q5)
  |                                         |         L20: SM105BLAssembly_SM105BLOutputBracket
  |                                         |           +-- [fixed] LegAssembly_v28_1__fixed_06
  |                                         |               L22: LegAssembly_SM105BLLinkBracket
  |                                         |                 +-- [fixed] LegAssembly_v28_1__fixed_07
  |                                         |                     L24: LegLinkAssembly_rigid_01_2
  |                                         |                       +-- [fixed] LegAssembly_v28_1__fixed_02
  |                                         |                           L26: SM105BLAssembly_SM105BLLinkBracket_2
  |                                         |                             |-- [fixed] LegAssembly_v28_1__SM105BLAssembly_v19_2__fixed_01
  |                                         |                             |   L28: SM100_BL_ASM_159_ASM_rigid_01_2
  |                                         |                             |     +-- [revolute] LegAssembly_v28_1__SM105BLAssembly_v19_2__rot_01 (q7)
  |                                         |                             |         L32: SM105BLAssembly_SM105BLOutputBracket_2
  |                                         |                             |           +-- [fixed] LegAssembly_v28_1__fixed_08
  |                                         |                             |               L34: DSSERVO_RDS51150_BodyOnly_rigid_01_2
  |                                         |                             |                 +-- [revolute] LegAssembly_v28_1__RDS51150Assembly_v14_3__rot_01 (q9)
  |                                         |                             |                     L36: RDS51150Assembly_RDS51150OriginalOutputBracket_2
  |                                         |                             |                       +-- [fixed] LegAssembly_v28_1__fixed_09
  |                                         |                             |                           L38: LegAssembly_FootPlate
  |                                         |                             +-- [fixed] LegAssembly_v28_1__fixed_11
  |                                         |                                 L29: LegAssembly_LiPo3S
  |                                         +-- [fixed] LegAssembly_v28_1__fixed_10
  |                                             L17: LegAssembly_LiPo3S_2
  |-- [fixed] biped_fixed_02
  |   L2: DSSERVO_RDS51150_BodyOnly_rigid_01_4
  |     +-- [revolute] LegAssembly_v28_2__RDS51150Assembly_v14_2__rot_01 (q2)
  |         L5: RDS51150Assembly_RDS51150OriginalOutputBracket_3
  |           +-- [fixed] LegAssembly_v28_2__fixed_05
  |               L7: RDS51150Assembly_hip_RDS51150OriginalOutputBracket_2
  |                 +-- [continuous] LegAssembly_v28_2__RDS51150Assembly_hip_v2_1__rot_01 (q4)
  |                     L9: DSSERVO_RDS51150_BodyOnly_rigid_01_6
  |                       +-- [fixed] LegAssembly_v28_2__fixed_04
  |                           L11: LegAssembly_RDS51150LinkBracket_2
  |                             +-- [fixed] LegAssembly_v28_2__fixed_03
  |                                 L13: LegLinkAssembly_rigid_01_3
  |                                   +-- [fixed] LegAssembly_v28_2___18
  |                                       L15: SM105BLAssembly_SM105BLLinkBracket_3
  |                                         |-- [fixed] LegAssembly_v28_2__SM105BLAssembly_v19_1__fixed_01
  |                                         |   L18: SM100_BL_ASM_159_ASM_rigid_01_3
  |                                         |     +-- [revolute] LegAssembly_v28_2__SM105BLAssembly_v19_1__rot_01 (q6)
  |                                         |         L21: SM105BLAssembly_SM105BLOutputBracket_3
  |                                         |           +-- [fixed] LegAssembly_v28_2__fixed_06
  |                                         |               L23: LegAssembly_SM105BLLinkBracket_2
  |                                         |                 +-- [fixed] LegAssembly_v28_2__fixed_07
  |                                         |                     L25: LegLinkAssembly_rigid_01_4
  |                                         |                       +-- [fixed] LegAssembly_v28_2__fixed_02
  |                                         |                           L27: SM105BLAssembly_SM105BLLinkBracket_4
  |                                         |                             |-- [fixed] LegAssembly_v28_2__SM105BLAssembly_v19_2__fixed_01
  |                                         |                             |   L30: SM100_BL_ASM_159_ASM_rigid_01_4
  |                                         |                             |     +-- [revolute] LegAssembly_v28_2__SM105BLAssembly_v19_2__rot_01 (q8)
  |                                         |                             |         L33: SM105BLAssembly_SM105BLOutputBracket_4
  |                                         |                             |           +-- [fixed] LegAssembly_v28_2__fixed_08
  |                                         |                             |               L35: DSSERVO_RDS51150_BodyOnly_rigid_01_5
  |                                         |                             |                 +-- [revolute] LegAssembly_v28_2__RDS51150Assembly_v14_3__rot_01 (q10)
  |                                         |                             |                     L37: RDS51150Assembly_RDS51150OriginalOutputBracket_4
  |                                         |                             |                       +-- [fixed] LegAssembly_v28_2__fixed_09
  |                                         |                             |                           L39: LegAssembly_FootPlate_2
  |                                         |                             +-- [fixed] LegAssembly_v28_2__fixed_11
  |                                         |                                 L31: LegAssembly_LiPo3S_3
  |                                         +-- [fixed] LegAssembly_v28_2__fixed_10
  |                                             L19: LegAssembly_LiPo3S_4
  +-- [fixed] biped_fixed_03
      L3: PelvisBasket
```

## Transforms

## biped_fixed_01

$L_{0}$ **base_link** -> $L_{1}$ **DSSERVO_RDS51150_BodyOnly_rigid_01** (fixed)

- **origin xyz**: (0.0175, -0.02, -0.04) m
- **origin rpy**: (1.570796, 1.570796, -3.141593) rad

### Local Transform

$$
T^{0}_{1} = \begin{bmatrix}
0 & -1 & 0 & 0.0175 \\
0 & 0 & 1 & -0.02 \\
-1 & 0 & 0 & -0.04 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## biped_fixed_02

$L_{0}$ **base_link** -> $L_{2}$ **DSSERVO_RDS51150_BodyOnly_rigid_01_4** (fixed)

- **origin xyz**: (0.0175, -0.23, -0.04) m
- **origin rpy**: (1.570796, 1.570796, -3.141593) rad

### Local Transform

$$
T^{0}_{2} = \begin{bmatrix}
0 & -1 & 0 & 0.0175 \\
0 & 0 & 1 & -0.23 \\
-1 & 0 & 0 & -0.04 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## biped_fixed_03

$L_{0}$ **base_link** -> $L_{3}$ **PelvisBasket** (fixed)

- **origin xyz**: (-0.065, 0.015, 0.003) m
- **origin rpy**: (0, 0, -1.570796) rad

### Local Transform

$$
T^{0}_{3} = \begin{bmatrix}
0 & 1 & 0 & -0.065 \\
-1 & 0 & 0 & 0.015 \\
0 & 0 & 1 & 0.003 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__RDS51150Assembly_v14_2__rot_01

$L_{1}$ **DSSERVO_RDS51150_BodyOnly_rigid_01** -> $L_{4}$ **RDS51150Assembly_RDS51150OriginalOutputBracket** (revolute)
  Variable: $q_{1}$

- **origin xyz**: (0.0195, 0.0232, 0) m
- **origin rpy**: (1.570796, -1.570796, 0) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{1}_{4}(q_{1}) = T_{fixed} \cdot R_{axis}(q_{1})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & -1 & 0 & 0.0195 \\
0 & 0 & -1 & 0.0232 \\
1 & 0 & 0 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{1}) = \begin{bmatrix}
c_{1} & -s_{1} & 0 & 0 \\
s_{1} & c_{1} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__RDS51150Assembly_v14_2__rot_01

$L_{2}$ **DSSERVO_RDS51150_BodyOnly_rigid_01_4** -> $L_{5}$ **RDS51150Assembly_RDS51150OriginalOutputBracket_3** (revolute)
  Variable: $q_{2}$

- **origin xyz**: (0.0195, 0.0232, 0) m
- **origin rpy**: (1.570796, -1.570796, 0) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{2}_{5}(q_{2}) = T_{fixed} \cdot R_{axis}(q_{2})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & -1 & 0 & 0.0195 \\
0 & 0 & -1 & 0.0232 \\
1 & 0 & 0 & 0 \\
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

## LegAssembly_v28_1__fixed_05

$L_{4}$ **RDS51150Assembly_RDS51150OriginalOutputBracket** -> $L_{6}$ **RDS51150Assembly_hip_RDS51150OriginalOutputBracket** (fixed)

- **origin xyz**: (-0.00755, -0.0895, 0.03075) m
- **origin rpy**: (0, 0, 1.570796) rad

### Local Transform

$$
T^{4}_{6} = \begin{bmatrix}
0 & -1 & 0 & -0.00755 \\
1 & 0 & 0 & -0.0895 \\
0 & 0 & 1 & 0.03075 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__fixed_05

$L_{5}$ **RDS51150Assembly_RDS51150OriginalOutputBracket_3** -> $L_{7}$ **RDS51150Assembly_hip_RDS51150OriginalOutputBracket_2** (fixed)

- **origin xyz**: (-0.00755, -0.0895, 0.03075) m
- **origin rpy**: (0, 0, 1.570796) rad

### Local Transform

$$
T^{5}_{7} = \begin{bmatrix}
0 & -1 & 0 & -0.00755 \\
1 & 0 & 0 & -0.0895 \\
0 & 0 & 1 & 0.03075 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__RDS51150Assembly_hip_v2_1__rot_01

$L_{6}$ **RDS51150Assembly_hip_RDS51150OriginalOutputBracket** -> $L_{8}$ **DSSERVO_RDS51150_BodyOnly_rigid_01_3** (continuous)
  Variable: $q_{3}$

- **origin xyz**: (0.0195, 0.0232, 0) m
- **origin rpy**: (0, 0, -1.570796) rad
- **axis**: (0, 0, 1)

### Local Transform

$T^{6}_{8}(q_{3}) = T_{fixed} \cdot R_{axis}(q_{3})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & 1 & 0 & 0.0195 \\
-1 & 0 & 0 & 0.0232 \\
0 & 0 & 1 & 0 \\
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

## LegAssembly_v28_2__RDS51150Assembly_hip_v2_1__rot_01

$L_{7}$ **RDS51150Assembly_hip_RDS51150OriginalOutputBracket_2** -> $L_{9}$ **DSSERVO_RDS51150_BodyOnly_rigid_01_6** (continuous)
  Variable: $q_{4}$

- **origin xyz**: (0.0195, 0.0232, 0) m
- **origin rpy**: (0, 0, -1.570796) rad
- **axis**: (0, 0, 1)

### Local Transform

$T^{7}_{9}(q_{4}) = T_{fixed} \cdot R_{axis}(q_{4})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & 1 & 0 & 0.0195 \\
-1 & 0 & 0 & 0.0232 \\
0 & 0 & 1 & 0 \\
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

## LegAssembly_v28_1__fixed_04

$L_{8}$ **DSSERVO_RDS51150_BodyOnly_rigid_01_3** -> $L_{10}$ **LegAssembly_RDS51150LinkBracket** (fixed)

- **origin xyz**: (0.0307, -0.0595, 0) m
- **origin rpy**: (-1.570796, 0, -3.141593) rad

### Local Transform

$$
T^{8}_{10} = \begin{bmatrix}
-1 & 0 & 0 & 0.0307 \\
0 & 0 & -1 & -0.0595 \\
0 & -1 & 0 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__fixed_04

$L_{9}$ **DSSERVO_RDS51150_BodyOnly_rigid_01_6** -> $L_{11}$ **LegAssembly_RDS51150LinkBracket_2** (fixed)

- **origin xyz**: (0.0307, -0.0595, 0) m
- **origin rpy**: (-1.570796, 0, -3.141593) rad

### Local Transform

$$
T^{9}_{11} = \begin{bmatrix}
-1 & 0 & 0 & 0.0307 \\
0 & 0 & -1 & -0.0595 \\
0 & -1 & 0 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__fixed_03

$L_{10}$ **LegAssembly_RDS51150LinkBracket** -> $L_{12}$ **LegLinkAssembly_rigid_01** (fixed)

- **origin xyz**: (-0.0355, 0.02, 0.2065) m
- **origin rpy**: (3.141593, 1.570796, 0) rad

### Local Transform

$$
T^{10}_{12} = \begin{bmatrix}
0 & 0 & -1 & -0.0355 \\
0 & -1 & 0 & 0.02 \\
-1 & 0 & 0 & 0.2065 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__fixed_03

$L_{11}$ **LegAssembly_RDS51150LinkBracket_2** -> $L_{13}$ **LegLinkAssembly_rigid_01_3** (fixed)

- **origin xyz**: (-0.0355, 0.02, 0.2065) m
- **origin rpy**: (3.141593, 1.570796, 0) rad

### Local Transform

$$
T^{11}_{13} = \begin{bmatrix}
0 & 0 & -1 & -0.0355 \\
0 & -1 & 0 & 0.02 \\
-1 & 0 & 0 & 0.2065 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1___18

$L_{12}$ **LegLinkAssembly_rigid_01** -> $L_{14}$ **SM105BLAssembly_SM105BLLinkBracket** (fixed)

- **origin xyz**: (-0.0065, 0.02, -0.0355) m
- **origin rpy**: (0, 1.570796, 0) rad

### Local Transform

$$
T^{12}_{14} = \begin{bmatrix}
0 & 0 & 1 & -0.0065 \\
0 & 1 & 0 & 0.02 \\
-1 & 0 & 0 & -0.0355 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2___18

$L_{13}$ **LegLinkAssembly_rigid_01_3** -> $L_{15}$ **SM105BLAssembly_SM105BLLinkBracket_3** (fixed)

- **origin xyz**: (-0.0065, 0.02, -0.0355) m
- **origin rpy**: (0, 1.570796, 0) rad

### Local Transform

$$
T^{13}_{15} = \begin{bmatrix}
0 & 0 & 1 & -0.0065 \\
0 & 1 & 0 & 0.02 \\
-1 & 0 & 0 & -0.0355 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__SM105BLAssembly_v19_1__fixed_01

$L_{14}$ **SM105BLAssembly_SM105BLLinkBracket** -> $L_{16}$ **SM100_BL_ASM_159_ASM_rigid_01** (fixed)

- **origin xyz**: (0.022, 0, -0.02925) m
- **origin rpy**: (1.570796, -1.570796, 0) rad

### Local Transform

$$
T^{14}_{16} = \begin{bmatrix}
0 & -1 & 0 & 0.022 \\
0 & 0 & -1 & 0 \\
1 & 0 & 0 & -0.02925 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__fixed_10

$L_{14}$ **SM105BLAssembly_SM105BLLinkBracket** -> $L_{17}$ **LegAssembly_LiPo3S_2** (fixed)

- **origin xyz**: (0.02, -0.012, 0.133) m
- **origin rpy**: (-1.570796, 1.570796, 0) rad

### Local Transform

$$
T^{14}_{17} = \begin{bmatrix}
0 & -1 & 0 & 0.02 \\
0 & 0 & 1 & -0.012 \\
-1 & 0 & 0 & 0.133 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__SM105BLAssembly_v19_1__fixed_01

$L_{15}$ **SM105BLAssembly_SM105BLLinkBracket_3** -> $L_{18}$ **SM100_BL_ASM_159_ASM_rigid_01_3** (fixed)

- **origin xyz**: (0.022, 0, -0.02925) m
- **origin rpy**: (1.570796, -1.570796, 0) rad

### Local Transform

$$
T^{15}_{18} = \begin{bmatrix}
0 & -1 & 0 & 0.022 \\
0 & 0 & -1 & 0 \\
1 & 0 & 0 & -0.02925 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__fixed_10

$L_{15}$ **SM105BLAssembly_SM105BLLinkBracket_3** -> $L_{19}$ **LegAssembly_LiPo3S_4** (fixed)

- **origin xyz**: (0.02, -0.012, 0.133) m
- **origin rpy**: (-1.570796, 1.570796, 0) rad

### Local Transform

$$
T^{15}_{19} = \begin{bmatrix}
0 & -1 & 0 & 0.02 \\
0 & 0 & 1 & -0.012 \\
-1 & 0 & 0 & 0.133 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__SM105BLAssembly_v19_1__rot_01

$L_{16}$ **SM100_BL_ASM_159_ASM_rigid_01** -> $L_{20}$ **SM105BLAssembly_SM105BLOutputBracket** (revolute)
  Variable: $q_{5}$

- **origin xyz**: (-0.0155, -0.0031, 0) m
- **origin rpy**: (-3.141593, 0, 1.570796) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{16}_{20}(q_{5}) = T_{fixed} \cdot R_{axis}(q_{5})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & 1 & 0 & -0.0155 \\
1 & 0 & 0 & -0.0031 \\
0 & 0 & -1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{5}) = \begin{bmatrix}
c_{5} & -s_{5} & 0 & 0 \\
s_{5} & c_{5} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__SM105BLAssembly_v19_1__rot_01

$L_{18}$ **SM100_BL_ASM_159_ASM_rigid_01_3** -> $L_{21}$ **SM105BLAssembly_SM105BLOutputBracket_3** (revolute)
  Variable: $q_{6}$

- **origin xyz**: (-0.0155, -0.0031, 0) m
- **origin rpy**: (-3.141593, 0, 1.570796) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{18}_{21}(q_{6}) = T_{fixed} \cdot R_{axis}(q_{6})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & 1 & 0 & -0.0155 \\
1 & 0 & 0 & -0.0031 \\
0 & 0 & -1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{6}) = \begin{bmatrix}
c_{6} & -s_{6} & 0 & 0 \\
s_{6} & c_{6} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__fixed_06

$L_{20}$ **SM105BLAssembly_SM105BLOutputBracket** -> $L_{22}$ **LegAssembly_SM105BLLinkBracket** (fixed)

- **origin xyz**: (0.025, -0.032, 0) m
- **origin rpy**: (-1.570796, 0, 3.141593) rad

### Local Transform

$$
T^{20}_{22} = \begin{bmatrix}
-1 & 0 & 0 & 0.025 \\
0 & 0 & -1 & -0.032 \\
0 & -1 & 0 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__fixed_06

$L_{21}$ **SM105BLAssembly_SM105BLOutputBracket_3** -> $L_{23}$ **LegAssembly_SM105BLLinkBracket_2** (fixed)

- **origin xyz**: (0.025, -0.032, 0) m
- **origin rpy**: (-1.570796, 0, 3.141593) rad

### Local Transform

$$
T^{21}_{23} = \begin{bmatrix}
-1 & 0 & 0 & 0.025 \\
0 & 0 & -1 & -0.032 \\
0 & -1 & 0 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__fixed_07

$L_{22}$ **LegAssembly_SM105BLLinkBracket** -> $L_{24}$ **LegLinkAssembly_rigid_01_2** (fixed)

- **origin xyz**: (-0.0355, 0.02, 0.2065) m
- **origin rpy**: (3.141593, 1.570796, 0) rad

### Local Transform

$$
T^{22}_{24} = \begin{bmatrix}
0 & 0 & -1 & -0.0355 \\
0 & -1 & 0 & 0.02 \\
-1 & 0 & 0 & 0.2065 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__fixed_07

$L_{23}$ **LegAssembly_SM105BLLinkBracket_2** -> $L_{25}$ **LegLinkAssembly_rigid_01_4** (fixed)

- **origin xyz**: (-0.0355, 0.02, 0.2065) m
- **origin rpy**: (3.141593, 1.570796, 0) rad

### Local Transform

$$
T^{23}_{25} = \begin{bmatrix}
0 & 0 & -1 & -0.0355 \\
0 & -1 & 0 & 0.02 \\
-1 & 0 & 0 & 0.2065 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__fixed_02

$L_{24}$ **LegLinkAssembly_rigid_01_2** -> $L_{26}$ **SM105BLAssembly_SM105BLLinkBracket_2** (fixed)

- **origin xyz**: (-0.0065, 0.02, -0.0355) m
- **origin rpy**: (0, 1.570796, 0) rad

### Local Transform

$$
T^{24}_{26} = \begin{bmatrix}
0 & 0 & 1 & -0.0065 \\
0 & 1 & 0 & 0.02 \\
-1 & 0 & 0 & -0.0355 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__fixed_02

$L_{25}$ **LegLinkAssembly_rigid_01_4** -> $L_{27}$ **SM105BLAssembly_SM105BLLinkBracket_4** (fixed)

- **origin xyz**: (-0.0065, 0.02, -0.0355) m
- **origin rpy**: (0, 1.570796, 0) rad

### Local Transform

$$
T^{25}_{27} = \begin{bmatrix}
0 & 0 & 1 & -0.0065 \\
0 & 1 & 0 & 0.02 \\
-1 & 0 & 0 & -0.0355 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__SM105BLAssembly_v19_2__fixed_01

$L_{26}$ **SM105BLAssembly_SM105BLLinkBracket_2** -> $L_{28}$ **SM100_BL_ASM_159_ASM_rigid_01_2** (fixed)

- **origin xyz**: (0.022, 0, -0.02925) m
- **origin rpy**: (1.570796, -1.570796, 0) rad

### Local Transform

$$
T^{26}_{28} = \begin{bmatrix}
0 & -1 & 0 & 0.022 \\
0 & 0 & -1 & 0 \\
1 & 0 & 0 & -0.02925 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__fixed_11

$L_{26}$ **SM105BLAssembly_SM105BLLinkBracket_2** -> $L_{29}$ **LegAssembly_LiPo3S** (fixed)

- **origin xyz**: (-0.02, 0.012, 0.133) m
- **origin rpy**: (1.570796, 1.570796, 0) rad

### Local Transform

$$
T^{26}_{29} = \begin{bmatrix}
0 & 1 & 0 & -0.02 \\
0 & 0 & -1 & 0.012 \\
-1 & 0 & 0 & 0.133 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__SM105BLAssembly_v19_2__fixed_01

$L_{27}$ **SM105BLAssembly_SM105BLLinkBracket_4** -> $L_{30}$ **SM100_BL_ASM_159_ASM_rigid_01_4** (fixed)

- **origin xyz**: (0.022, 0, -0.02925) m
- **origin rpy**: (1.570796, -1.570796, 0) rad

### Local Transform

$$
T^{27}_{30} = \begin{bmatrix}
0 & -1 & 0 & 0.022 \\
0 & 0 & -1 & 0 \\
1 & 0 & 0 & -0.02925 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__fixed_11

$L_{27}$ **SM105BLAssembly_SM105BLLinkBracket_4** -> $L_{31}$ **LegAssembly_LiPo3S_3** (fixed)

- **origin xyz**: (-0.02, 0.012, 0.133) m
- **origin rpy**: (1.570796, 1.570796, 0) rad

### Local Transform

$$
T^{27}_{31} = \begin{bmatrix}
0 & 1 & 0 & -0.02 \\
0 & 0 & -1 & 0.012 \\
-1 & 0 & 0 & 0.133 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__SM105BLAssembly_v19_2__rot_01

$L_{28}$ **SM100_BL_ASM_159_ASM_rigid_01_2** -> $L_{32}$ **SM105BLAssembly_SM105BLOutputBracket_2** (revolute)
  Variable: $q_{7}$

- **origin xyz**: (-0.0155, -0.0031, 0) m
- **origin rpy**: (-3.141593, 0, 1.570796) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{28}_{32}(q_{7}) = T_{fixed} \cdot R_{axis}(q_{7})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & 1 & 0 & -0.0155 \\
1 & 0 & 0 & -0.0031 \\
0 & 0 & -1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{7}) = \begin{bmatrix}
c_{7} & -s_{7} & 0 & 0 \\
s_{7} & c_{7} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__SM105BLAssembly_v19_2__rot_01

$L_{30}$ **SM100_BL_ASM_159_ASM_rigid_01_4** -> $L_{33}$ **SM105BLAssembly_SM105BLOutputBracket_4** (revolute)
  Variable: $q_{8}$

- **origin xyz**: (-0.0155, -0.0031, 0) m
- **origin rpy**: (-3.141593, 0, 1.570796) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{30}_{33}(q_{8}) = T_{fixed} \cdot R_{axis}(q_{8})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & 1 & 0 & -0.0155 \\
1 & 0 & 0 & -0.0031 \\
0 & 0 & -1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{8}) = \begin{bmatrix}
c_{8} & -s_{8} & 0 & 0 \\
s_{8} & c_{8} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__fixed_08

$L_{32}$ **SM105BLAssembly_SM105BLOutputBracket_2** -> $L_{34}$ **DSSERVO_RDS51150_BodyOnly_rigid_01_2** (fixed)

- **origin xyz**: (0.0255, -0.072, -0.009) m
- **origin rpy**: (-1.570796, 0, -1.570796) rad

### Local Transform

$$
T^{32}_{34} = \begin{bmatrix}
0 & 0 & 1 & 0.0255 \\
-1 & 0 & 0 & -0.072 \\
0 & -1 & 0 & -0.009 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__fixed_08

$L_{33}$ **SM105BLAssembly_SM105BLOutputBracket_4** -> $L_{35}$ **DSSERVO_RDS51150_BodyOnly_rigid_01_5** (fixed)

- **origin xyz**: (0.0255, -0.072, -0.009) m
- **origin rpy**: (-1.570796, 0, -1.570796) rad

### Local Transform

$$
T^{33}_{35} = \begin{bmatrix}
0 & 0 & 1 & 0.0255 \\
-1 & 0 & 0 & -0.072 \\
0 & -1 & 0 & -0.009 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_1__RDS51150Assembly_v14_3__rot_01

$L_{34}$ **DSSERVO_RDS51150_BodyOnly_rigid_01_2** -> $L_{36}$ **RDS51150Assembly_RDS51150OriginalOutputBracket_2** (revolute)
  Variable: $q_{9}$

- **origin xyz**: (0.0195, 0.0232, 0) m
- **origin rpy**: (1.570796, -1.570796, 0) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{34}_{36}(q_{9}) = T_{fixed} \cdot R_{axis}(q_{9})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & -1 & 0 & 0.0195 \\
0 & 0 & -1 & 0.0232 \\
1 & 0 & 0 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

$$
R_{axis}(q_{9}) = \begin{bmatrix}
c_{9} & -s_{9} & 0 & 0 \\
s_{9} & c_{9} & 0 & 0 \\
0 & 0 & 1 & 0 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__RDS51150Assembly_v14_3__rot_01

$L_{35}$ **DSSERVO_RDS51150_BodyOnly_rigid_01_5** -> $L_{37}$ **RDS51150Assembly_RDS51150OriginalOutputBracket_4** (revolute)
  Variable: $q_{10}$

- **origin xyz**: (0.0195, 0.0232, 0) m
- **origin rpy**: (1.570796, -1.570796, 0) rad
- **axis**: (0, 0, 1)
- **limits**: [-0.698132, 0.698132] rad ([-40deg, 40deg])

### Local Transform

$T^{35}_{37}(q_{10}) = T_{fixed} \cdot R_{axis}(q_{10})$ where:

$$
T_{fixed} = \begin{bmatrix}
0 & -1 & 0 & 0.0195 \\
0 & 0 & -1 & 0.0232 \\
1 & 0 & 0 & 0 \\
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

## LegAssembly_v28_1__fixed_09

$L_{36}$ **RDS51150Assembly_RDS51150OriginalOutputBracket_2** -> $L_{38}$ **LegAssembly_FootPlate** (fixed)

- **origin xyz**: (0, -0.035, -0.01425) m
- **origin rpy**: (1.570796, 0, 3.141593) rad

### Local Transform

$$
T^{36}_{38} = \begin{bmatrix}
-1 & 0 & 0 & 0 \\
0 & 0 & 1 & -0.035 \\
0 & 1 & 0 & -0.01425 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## LegAssembly_v28_2__fixed_09

$L_{37}$ **RDS51150Assembly_RDS51150OriginalOutputBracket_4** -> $L_{39}$ **LegAssembly_FootPlate_2** (fixed)

- **origin xyz**: (0, -0.035, -0.01425) m
- **origin rpy**: (1.570796, 0, 3.141593) rad

### Local Transform

$$
T^{37}_{39} = \begin{bmatrix}
-1 & 0 & 0 & 0 \\
0 & 0 & 1 & -0.035 \\
0 & 1 & 0 & -0.01425 \\
0 & 0 & 0 & 1 \\
\end{bmatrix}
$$

---

## Global Transform Chains

Transform from root $L_0$ to any link, as product of local transforms along the kinematic chain.

$$T^{0}_{4} = T^{0}_{1} \cdot T^{1}_{4}(q_{1})\quad (L_0 \to L_{4}: \text{RDS51150Assembly_RDS51150OriginalOutputBracket})$$

$$T^{0}_{5} = T^{0}_{2} \cdot T^{2}_{5}(q_{2})\quad (L_0 \to L_{5}: \text{RDS51150Assembly_RDS51150OriginalOutputBracket_3})$$

$$T^{0}_{6} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6}\quad (L_0 \to L_{6}: \text{RDS51150Assembly_hip_RDS51150OriginalOutputBracket})$$

$$T^{0}_{7} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7}\quad (L_0 \to L_{7}: \text{RDS51150Assembly_hip_RDS51150OriginalOutputBracket_2})$$

$$T^{0}_{8} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3})\quad (L_0 \to L_{8}: \text{DSSERVO_RDS51150_BodyOnly_rigid_01_3})$$

$$T^{0}_{9} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4})\quad (L_0 \to L_{9}: \text{DSSERVO_RDS51150_BodyOnly_rigid_01_6})$$

$$T^{0}_{10} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10}\quad (L_0 \to L_{10}: \text{LegAssembly_RDS51150LinkBracket})$$

$$T^{0}_{11} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11}\quad (L_0 \to L_{11}: \text{LegAssembly_RDS51150LinkBracket_2})$$

$$T^{0}_{12} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12}\quad (L_0 \to L_{12}: \text{LegLinkAssembly_rigid_01})$$

$$T^{0}_{13} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13}\quad (L_0 \to L_{13}: \text{LegLinkAssembly_rigid_01_3})$$

$$T^{0}_{14} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14}\quad (L_0 \to L_{14}: \text{SM105BLAssembly_SM105BLLinkBracket})$$

$$T^{0}_{15} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15}\quad (L_0 \to L_{15}: \text{SM105BLAssembly_SM105BLLinkBracket_3})$$

$$T^{0}_{16} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16}\quad (L_0 \to L_{16}: \text{SM100_BL_ASM_159_ASM_rigid_01})$$

$$T^{0}_{17} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{17}\quad (L_0 \to L_{17}: \text{LegAssembly_LiPo3S_2})$$

$$T^{0}_{18} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18}\quad (L_0 \to L_{18}: \text{SM100_BL_ASM_159_ASM_rigid_01_3})$$

$$T^{0}_{19} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{19}\quad (L_0 \to L_{19}: \text{LegAssembly_LiPo3S_4})$$

$$T^{0}_{20} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16} \cdot T^{16}_{20}(q_{5})\quad (L_0 \to L_{20}: \text{SM105BLAssembly_SM105BLOutputBracket})$$

$$T^{0}_{21} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18} \cdot T^{18}_{21}(q_{6})\quad (L_0 \to L_{21}: \text{SM105BLAssembly_SM105BLOutputBracket_3})$$

$$T^{0}_{22} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16} \cdot T^{16}_{20}(q_{5}) \cdot T^{20}_{22}\quad (L_0 \to L_{22}: \text{LegAssembly_SM105BLLinkBracket})$$

$$T^{0}_{23} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18} \cdot T^{18}_{21}(q_{6}) \cdot T^{21}_{23}\quad (L_0 \to L_{23}: \text{LegAssembly_SM105BLLinkBracket_2})$$

$$T^{0}_{24} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16} \cdot T^{16}_{20}(q_{5}) \cdot T^{20}_{22} \cdot T^{22}_{24}\quad (L_0 \to L_{24}: \text{LegLinkAssembly_rigid_01_2})$$

$$T^{0}_{25} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18} \cdot T^{18}_{21}(q_{6}) \cdot T^{21}_{23} \cdot T^{23}_{25}\quad (L_0 \to L_{25}: \text{LegLinkAssembly_rigid_01_4})$$

$$T^{0}_{26} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16} \cdot T^{16}_{20}(q_{5}) \cdot T^{20}_{22} \cdot T^{22}_{24} \cdot T^{24}_{26}\quad (L_0 \to L_{26}: \text{SM105BLAssembly_SM105BLLinkBracket_2})$$

$$T^{0}_{27} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18} \cdot T^{18}_{21}(q_{6}) \cdot T^{21}_{23} \cdot T^{23}_{25} \cdot T^{25}_{27}\quad (L_0 \to L_{27}: \text{SM105BLAssembly_SM105BLLinkBracket_4})$$

$$T^{0}_{28} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16} \cdot T^{16}_{20}(q_{5}) \cdot T^{20}_{22} \cdot T^{22}_{24} \cdot T^{24}_{26} \cdot T^{26}_{28}\quad (L_0 \to L_{28}: \text{SM100_BL_ASM_159_ASM_rigid_01_2})$$

$$T^{0}_{29} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16} \cdot T^{16}_{20}(q_{5}) \cdot T^{20}_{22} \cdot T^{22}_{24} \cdot T^{24}_{26} \cdot T^{26}_{29}\quad (L_0 \to L_{29}: \text{LegAssembly_LiPo3S})$$

$$T^{0}_{30} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18} \cdot T^{18}_{21}(q_{6}) \cdot T^{21}_{23} \cdot T^{23}_{25} \cdot T^{25}_{27} \cdot T^{27}_{30}\quad (L_0 \to L_{30}: \text{SM100_BL_ASM_159_ASM_rigid_01_4})$$

$$T^{0}_{31} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18} \cdot T^{18}_{21}(q_{6}) \cdot T^{21}_{23} \cdot T^{23}_{25} \cdot T^{25}_{27} \cdot T^{27}_{31}\quad (L_0 \to L_{31}: \text{LegAssembly_LiPo3S_3})$$

$$T^{0}_{32} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16} \cdot T^{16}_{20}(q_{5}) \cdot T^{20}_{22} \cdot T^{22}_{24} \cdot T^{24}_{26} \cdot T^{26}_{28} \cdot T^{28}_{32}(q_{7})\quad (L_0 \to L_{32}: \text{SM105BLAssembly_SM105BLOutputBracket_2})$$

$$T^{0}_{33} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18} \cdot T^{18}_{21}(q_{6}) \cdot T^{21}_{23} \cdot T^{23}_{25} \cdot T^{25}_{27} \cdot T^{27}_{30} \cdot T^{30}_{33}(q_{8})\quad (L_0 \to L_{33}: \text{SM105BLAssembly_SM105BLOutputBracket_4})$$

$$T^{0}_{34} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16} \cdot T^{16}_{20}(q_{5}) \cdot T^{20}_{22} \cdot T^{22}_{24} \cdot T^{24}_{26} \cdot T^{26}_{28} \cdot T^{28}_{32}(q_{7}) \cdot T^{32}_{34}\quad (L_0 \to L_{34}: \text{DSSERVO_RDS51150_BodyOnly_rigid_01_2})$$

$$T^{0}_{35} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18} \cdot T^{18}_{21}(q_{6}) \cdot T^{21}_{23} \cdot T^{23}_{25} \cdot T^{25}_{27} \cdot T^{27}_{30} \cdot T^{30}_{33}(q_{8}) \cdot T^{33}_{35}\quad (L_0 \to L_{35}: \text{DSSERVO_RDS51150_BodyOnly_rigid_01_5})$$

$$T^{0}_{36} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16} \cdot T^{16}_{20}(q_{5}) \cdot T^{20}_{22} \cdot T^{22}_{24} \cdot T^{24}_{26} \cdot T^{26}_{28} \cdot T^{28}_{32}(q_{7}) \cdot T^{32}_{34} \cdot T^{34}_{36}(q_{9})\quad (L_0 \to L_{36}: \text{RDS51150Assembly_RDS51150OriginalOutputBracket_2})$$

$$T^{0}_{37} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18} \cdot T^{18}_{21}(q_{6}) \cdot T^{21}_{23} \cdot T^{23}_{25} \cdot T^{25}_{27} \cdot T^{27}_{30} \cdot T^{30}_{33}(q_{8}) \cdot T^{33}_{35} \cdot T^{35}_{37}(q_{10})\quad (L_0 \to L_{37}: \text{RDS51150Assembly_RDS51150OriginalOutputBracket_4})$$

$$T^{0}_{38} = T^{0}_{1} \cdot T^{1}_{4}(q_{1}) \cdot T^{4}_{6} \cdot T^{6}_{8}(q_{3}) \cdot T^{8}_{10} \cdot T^{10}_{12} \cdot T^{12}_{14} \cdot T^{14}_{16} \cdot T^{16}_{20}(q_{5}) \cdot T^{20}_{22} \cdot T^{22}_{24} \cdot T^{24}_{26} \cdot T^{26}_{28} \cdot T^{28}_{32}(q_{7}) \cdot T^{32}_{34} \cdot T^{34}_{36}(q_{9}) \cdot T^{36}_{38}\quad (L_0 \to L_{38}: \text{LegAssembly_FootPlate})$$

$$T^{0}_{39} = T^{0}_{2} \cdot T^{2}_{5}(q_{2}) \cdot T^{5}_{7} \cdot T^{7}_{9}(q_{4}) \cdot T^{9}_{11} \cdot T^{11}_{13} \cdot T^{13}_{15} \cdot T^{15}_{18} \cdot T^{18}_{21}(q_{6}) \cdot T^{21}_{23} \cdot T^{23}_{25} \cdot T^{25}_{27} \cdot T^{27}_{30} \cdot T^{30}_{33}(q_{8}) \cdot T^{33}_{35} \cdot T^{35}_{37}(q_{10}) \cdot T^{37}_{39}\quad (L_0 \to L_{39}: \text{LegAssembly_FootPlate_2})$$

