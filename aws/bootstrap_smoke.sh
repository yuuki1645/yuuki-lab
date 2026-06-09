#!/bin/bash
set -euxo pipefail
exec > /var/log/yuuki-bootstrap.log 2>&1

SEED="${SEED:-1}"
RUN_NAME="${RUN_NAME:-aws_smoke_seed${SEED}_$(date +%Y%m%d_%H%M%S)}"
BUCKET="${BUCKET:-yuuki-lab-runs-dev}"
REPO_URL="${REPO_URL:-https://github.com/yuuki1645/yuuki-lab.git}"
BRANCH="${BRANCH:-main}"

export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y git python3-pip python3-venv \
  libgl1 libglib2.0-0 libglew2.2 libosmesa6 awscli

rm -rf /opt/yuuki-lab
git clone --branch "${BRANCH}" --depth 1 "${REPO_URL}" /opt/yuuki-lab

cd /opt/yuuki-lab/mujoco-sim/mujoco_rl_sim/experiments/exp_030_biped_ppo_walk

python3 -m venv /opt/yuuki-venv
source /opt/yuuki-venv/bin/activate

pip install --upgrade pip
pip install -r requirements-cpu.txt

python -m contract validate

python train.py \
  training.num_updates=50 \
  runtime=fast \
  wandb=disabled \
  training.seed="${SEED}"

RUNS_DIR="/opt/yuuki-lab/mujoco-sim/mujoco_rl_sim/runs/exp_030_biped_ppo_walk"
aws s3 sync "${RUNS_DIR}/" "s3://${BUCKET}/aws-test/${RUN_NAME}/runs/" --region ap-northeast-1 || true
aws s3 cp /var/log/yuuki-bootstrap.log "s3://${BUCKET}/aws-test/${RUN_NAME}/bootstrap.log" --region ap-northeast-1

echo "[done] s3://${BUCKET}/aws-test/${RUN_NAME}/"