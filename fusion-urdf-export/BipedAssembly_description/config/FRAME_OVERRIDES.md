# Frame overrides

The exporter changes coordinate frames without changing mesh vertices.

- `rule=auto`: root uses Fusion design world (X forward, Z up); a
  revolute/continuous child uses local +Z as its rotation axis.
- `rule=keep`: keep the original extracted link orientation.
- `rule=world_rpy`: for a non-root link, use `post_roll_deg`, `post_pitch_deg`, and
  `post_yaw_deg` as the link frame's absolute zero-pose orientation in the
  Fusion design-world frame.

The URDF root frame is the URDF world and is therefore always handled by
`auto`/`keep`; an arbitrary root RPY would need an extra wrapper link.

The `original_*` columns are regenerated reference values. Edit only `rule`
and the `post_*` columns. Translations are intentionally unsupported because
an arbitrary translated revolute frame would change the physical rotation.

After editing, regenerate only URDF/Xacro/YAML/docs (no Fusion mesh export):

```powershell
# From the fusion2URDF repository root:
python tools/reframe.py <path-to-description-package>
```

From the directory containing the checkout, the equivalent module command is
`python -m fusion2URDF.tools.reframe <path-to-description-package>`.
