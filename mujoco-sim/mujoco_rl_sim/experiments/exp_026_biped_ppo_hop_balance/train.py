"""exp_026 学習エントリ（exp_025 同等・拡大 MLP・スタンドアロン ``contract`` 同梱）。"""

from __future__ import annotations

from _paths import install

install()

from pathlib import Path
from typing import Any

from contract import PpoTrainBindings, run_ppo_train

import checkpoint
import config
import wandb_logging
from agent import AgentPPO
from env import EnvBipedPPO
from experiment_contract import TELEMETRY_CONTRACT
from package_meta import EXP_NAME
import warmup
from run_config import TrainRunConfig, parse_train_args


def _load_resume_state(resume_path: Path) -> dict[str, Any]:
  return checkpoint.load_checkpoint(resume_path, map_location="cpu")


def _create_agent(run: TrainRunConfig) -> tuple[AgentPPO, dict[str, Any] | None]:
  if run.resume_path is None:
    agent = AgentPPO(obs_dim=config.OBS_DIM)
    if run.lr is not None:
      agent.set_learning_rate(run.lr)
    return agent, None

  payload = _load_resume_state(run.resume_path)
  agent = AgentPPO.from_checkpoint(
    run.resume_path,
    lr=run.lr,
    load_optimizer=run.load_optimizer,
  )
  return agent, payload


def _wandb_init(run: TrainRunConfig, payload: dict[str, Any] | None) -> None:
  extra_config: dict[str, Any] | None = None
  extra_tags: tuple[str, ...] | None = None
  run_name = run.wandb_run_name

  if payload is not None:
    base_update = int(payload.get("update", 0))
    base_env_steps = int(payload.get("total_env_steps", 0))
    base_episodes = int(payload.get("episodes_finished", 0))
    extra_config = {
      "resume_checkpoint": str(run.resume_path),
      "resume_base_update": base_update,
      "resume_base_env_steps": base_env_steps,
      "resume_base_episodes_finished": base_episodes,
      "num_updates_this_run": run.num_updates,
      "end_update_target": base_update + run.num_updates,
      "telemetry_schema": TELEMETRY_CONTRACT.schema_id,
      "contract_package": "contract",
    }
    if run.lr is not None:
      extra_config["lr"] = run.lr
      extra_config["lr_overridden"] = True
    else:
      extra_config["lr_overridden"] = False
    extra_tags = ("finetune", "resume", "contract")
    if run_name is None:
      lr_tag = f"lr{run.lr:g}" if run.lr is not None else "lr_ckpt"
      run_name = f"resume_u{base_update:06d}_{lr_tag}"
  else:
    extra_config = {
      "telemetry_schema": TELEMETRY_CONTRACT.schema_id,
      "contract_package": "contract",
    }
    extra_tags = ("contract",)

  wandb_logging.init(
    extra_config=extra_config,
    extra_tags=extra_tags,
    run_name=run_name,
    enabled=run.wandb,
  )


def main() -> None:
  run = parse_train_args()
  bindings = PpoTrainBindings(
    config=config,
    checkpoint=checkpoint,
    wandb_logging=wandb_logging,
    warmup=warmup,
    exp_name=EXP_NAME,
    telemetry=TELEMETRY_CONTRACT,
    env_factory=lambda viewer: EnvBipedPPO(enable_viewer=viewer),
    create_agent=_create_agent,
    init_wandb=_wandb_init,
    train_run_config=run,
  )
  run_ppo_train(bindings)


if __name__ == "__main__":
  main()
