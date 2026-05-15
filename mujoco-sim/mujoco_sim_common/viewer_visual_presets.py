# type: ignore

import mujoco

def apply_model_visual_preset(model):
  model.vis.map.alpha = 0.5
  model.vis.scale.jointlength = 0.3
  model.vis.scale.jointwidth = 0.1
  model.vis.scale.framelength = 0.8
  model.vis.scale.framewidth = 0.04
  model.vis.scale.com = 0.1
  model.vis.rgba.com = (1, 0, 0, 1)
  model.vis.headlight.ambient = 0.5
  model.vis.headlight.diffuse = 1
  model.vis.headlight.specular = 1

def apply_passive_viewer_options(viewer):
  viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_JOINT] = 0
  viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] = 1
  viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_COM] = 0
  viewer.opt.label = mujoco.mjtLabel.mjLABEL_SITE
  viewer.opt.frame = mujoco.mjtFrame.mjFRAME_SITE