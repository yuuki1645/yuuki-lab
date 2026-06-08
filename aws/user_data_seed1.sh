#!/bin/bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y awscli curl

export SEED=1
export RUN_NAME="aws_smoke_seed1_$(date +%Y%m%d)"
export BUCKET=yuuki-lab-runs-dev

aws s3 cp "s3://${BUCKET}/scripts/bootstrap_smoke.sh" /tmp/bootstrap.sh --region ap-northeast-1
chmod +x /tmp/bootstrap.sh
bash /tmp/bootstrap.sh

shutdown -h now