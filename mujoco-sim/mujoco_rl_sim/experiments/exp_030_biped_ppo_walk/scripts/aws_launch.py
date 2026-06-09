"""exp_030: AWS EC2 Spot に学習ジョブを投入するランチャー（新プロメテウス v0）。

自宅 PC から boto3 で Spot VM を起動し、各 VM が S3 上の bootstrap を実行して
``train.py`` を 1 本走らせる。1 job = 1 インスタンス。

**課金警告**: ``--confirm`` 付きで実行すると、**あなたの AWS アカウント**で Spot EC2 が
起動し課金が発生します。clone しただけでは何も起きません。

安全装置:

- ``aws_launch.config.toml`` の ``enabled = true``（明示 opt-in）
- 実起動には ``--confirm`` 必須
- 初回は ``--dry-run`` で計画だけ確認（AWS API を呼ばない）

使用例（exp_030 ルートで）::

  pip install -r ../../../../aws/requirements.txt
  cp ../../../../aws/aws_launch.config.example.toml ../../../../aws/aws_launch.config.toml
  # aws_launch.config.toml を編集（security_group_id 等）し enabled = true

  python scripts/aws_launch.py --dry-run
  python scripts/aws_launch.py --seeds 1,2,3,4 --confirm --upload-bootstrap
  python scripts/aws_launch.py --sweep sweeps/baseline_10seed.yaml --confirm

設定ファイル既定: リポジトリ ``aws/aws_launch.config.toml``
"""

from __future__ import annotations

import argparse
import datetime as dt
import random
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
  sys.path.insert(0, str(_ROOT))

# リポジトリルート（yuuki-lab/）
_REPO_ROOT = Path(__file__).resolve().parents[5]
_AWS_DIR = _REPO_ROOT / "aws"
_DEFAULT_CONFIG = _AWS_DIR / "aws_launch.config.toml"

# 同時起動の既定上限（いきなり 8 台は避ける）
_DEFAULT_PARALLEL = 4

_UBUNTU_OWNER = "099720109477"
_UBUNTU_NAME_FILTER = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"


@dataclass(frozen=True)
class LaunchJob:
  """1 回の EC2 起動 = 1 学習 run。"""

  seed: int
  sweep_id: str
  run_name: str
  tag_name: str


@dataclass(frozen=True)
class LaunchConfig:
  enabled: bool
  region: str
  ami_id: str
  instance_type: str
  security_group_id: str
  key_name: str
  iam_instance_profile: str
  s3_bucket: str
  bootstrap_s3_key: str
  bootstrap_local_path: Path
  ebs_volume_gb: int
  repo_branch: str


def _load_config(path: Path) -> LaunchConfig:
  if not path.is_file():
    raise FileNotFoundError(
      f"設定がありません: {path}\n"
      f"  cp {_AWS_DIR / 'aws_launch.config.example.toml'} {path}\n"
      "  を実行し、ami_id / security_group_id 等を編集してください。"
    )
  raw = tomllib.loads(path.read_text(encoding="utf-8"))
  bootstrap_local = str(raw.get("bootstrap_local_path", "aws/bootstrap_smoke.sh"))
  return LaunchConfig(
    enabled=bool(raw.get("enabled", False)),
    region=str(raw.get("region", "ap-northeast-1")),
    ami_id=str(raw.get("ami_id", "")).strip(),
    instance_type=str(raw.get("instance_type", "c7i.2xlarge")),
    security_group_id=str(raw["security_group_id"]).strip(),
    key_name=str(raw.get("key_name", "")).strip(),
    iam_instance_profile=str(raw["iam_instance_profile"]).strip(),
    s3_bucket=str(raw["s3_bucket"]).strip(),
    bootstrap_s3_key=str(raw.get("bootstrap_s3_key", "scripts/bootstrap_smoke.sh")).strip(),
    bootstrap_local_path=_REPO_ROOT / bootstrap_local,
    ebs_volume_gb=int(raw.get("ebs_volume_gb", 30)),
    repo_branch=str(raw.get("repo_branch", "main")),
  )


def _parse_seeds(text: str) -> tuple[int, ...]:
  parts = [p.strip() for p in text.split(",") if p.strip()]
  if not parts:
    raise ValueError("--seeds が空です")
  return tuple(int(p) for p in parts)


def _load_sweep_seeds(path: Path, *, shuffle_seed: int | None) -> tuple[str, tuple[int, ...]]:
  """sweep YAML から sweep_id と seed 一覧を読む（param_grid 非対応 v0）。"""
  try:
    import yaml
  except ImportError as exc:
    raise SystemExit("sweep YAML を読むには pip install pyyaml が必要です") from exc

  raw = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(raw, dict):
    raise ValueError(f"sweep YAML は mapping である必要があります: {path}")

  sweep_id = str(raw["sweep_id"]).strip()
  if raw.get("param_grid"):
    raise ValueError(
      "aws_launch v0 は param_grid 付き sweep 未対応です。"
      " --seeds を直接指定するか、param_grid: {} の sweep を使ってください。"
    )

  if "seeds" in raw:
    seeds = [int(s) for s in raw["seeds"]]
  elif "seed_count" in raw:
    start = int(raw.get("seed_start", 1))
    count = int(raw["seed_count"])
    seeds = list(range(start, start + count))
  else:
    raise ValueError("sweep に seeds または seed_count が必要です")

  shuffle = int(raw.get("shuffle_seed", 0)) if shuffle_seed is None else shuffle_seed
  rng = random.Random(shuffle)
  rng.shuffle(seeds)
  return sweep_id, tuple(seeds)


def _sanitize_tag(value: str, *, max_len: int = 128) -> str:
  s = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
  return (s or "job")[:max_len]


def _build_jobs(
  *,
  seeds: tuple[int, ...],
  sweep_id: str,
  parallel: int,
  date_stamp: str,
) -> list[LaunchJob]:
  """先頭 parallel 件だけ起動する（既定 parallel=4）。"""
  if parallel < 1:
    raise ValueError("--parallel は 1 以上")
  selected = seeds[:parallel]
  jobs: list[LaunchJob] = []
  for seed in selected:
    run_name = f"{sweep_id}_seed{seed}_{date_stamp}"
    tag_name = _sanitize_tag(f"yuuki-aws-{sweep_id}-seed{seed}")
    jobs.append(
      LaunchJob(
        seed=seed,
        sweep_id=sweep_id,
        run_name=run_name,
        tag_name=tag_name,
      )
    )
  return jobs


def _user_data_script(*, job: LaunchJob, cfg: LaunchConfig) -> str:
  """cloud-init に渡す bash（S3 bootstrap 取得 → 実行 → shutdown）。"""
  return f"""#!/bin/bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y awscli curl

export SEED={job.seed}
export RUN_NAME="{job.run_name}"
export BUCKET="{cfg.s3_bucket}"
export BRANCH="{cfg.repo_branch}"

aws s3 cp "s3://${{BUCKET}}/{cfg.bootstrap_s3_key}" /tmp/bootstrap.sh --region {cfg.region}
chmod +x /tmp/bootstrap.sh
bash /tmp/bootstrap.sh

shutdown -h now
"""


def _resolve_ami_id(ec2: Any, cfg: LaunchConfig) -> str:
  if cfg.ami_id:
    return cfg.ami_id
  out = ec2.describe_images(
    Owners=[_UBUNTU_OWNER],
    Filters=[{"Name": "name", "Values": [_UBUNTU_NAME_FILTER]}],
  )
  images = sorted(out.get("Images", []), key=lambda im: im.get("CreationDate", ""))
  if not images:
    raise RuntimeError(f"Ubuntu AMI が見つかりません: region={cfg.region}")
  return str(images[-1]["ImageId"])


def _try_aws_account_id(region: str) -> str | None:
  """設定済み認証情報の AWS アカウント ID（表示用。失敗時は None）。"""
  try:
    import boto3
  except ImportError:
    return None
  try:
    sts = boto3.client("sts", region_name=region)
    return str(sts.get_caller_identity()["Account"])
  except Exception:
    return None


def _print_launch_summary(
  *,
  cfg: LaunchConfig,
  jobs: list[LaunchJob],
  dry_run: bool,
  upload_bootstrap: bool,
  aws_account_id: str | None,
  ami_id: str | None,
) -> None:
  """起動前サマリ（課金・対象アカウントの確認用）。"""
  mode = "DRY-RUN（AWS API 呼び出しなし）" if dry_run else "本番起動（課金あり）"
  print("")
  print("=" * 60)
  print(f"[summary] {mode}")
  print("=" * 60)
  if aws_account_id:
    print(f"  AWS アカウント ID : {aws_account_id}")
  else:
    print("  AWS アカウント ID : （未取得。--dry-run または認証未設定）")
  print(f"  リージョン          : {cfg.region}")
  print(f"  インスタンスタイプ  : {cfg.instance_type} (Spot)")
  print(f"  起動台数            : {len(jobs)}")
  print(f"  seeds               : {[j.seed for j in jobs]}")
  print(f"  sweep_id            : {jobs[0].sweep_id if jobs else '-'}")
  print(f"  EBS ルート          : {cfg.ebs_volume_gb} GB gp3 / 台")
  print(f"  S3 バケット         : {cfg.s3_bucket}")
  if ami_id:
    print(f"  AMI                 : {ami_id}")
  else:
    print(f"  AMI                 : （起動時に Ubuntu 22.04 を自動解決）")
  if upload_bootstrap:
    print(f"  bootstrap upload    : s3://{cfg.s3_bucket}/{cfg.bootstrap_s3_key}")
  print(f"  config enabled      : {cfg.enabled}")
  if not dry_run:
    print("")
    print("  ※ 上記アカウントで Spot EC2 が起動します。意図したアカウントか確認してください。")
  print("=" * 60)
  print("")


def _guard_real_launch(*, cfg: LaunchConfig, confirm: bool) -> None:
  """本番起動前の安全チェック（enabled + --confirm）。"""
  if not cfg.enabled:
    raise SystemExit(
      "[abort] aws_launch.config.toml の enabled が true ではありません。\n"
      "  意図的に Spot を起動する場合のみ enabled = true に設定してください。\n"
      "  計画確認だけなら --dry-run を使ってください。"
    )
  if not confirm:
    raise SystemExit(
      "[abort] EC2 起動には --confirm が必要です。\n"
      "  1) python scripts/aws_launch.py --dry-run で計画を確認\n"
      "  2) 問題なければ同じ引数に --confirm を付けて再実行"
    )


def _upload_bootstrap(cfg: LaunchConfig) -> None:
  try:
    import boto3
  except ImportError as exc:
    raise SystemExit("pip install boto3 が必要です") from exc

  if not cfg.bootstrap_local_path.is_file():
    raise FileNotFoundError(f"bootstrap がありません: {cfg.bootstrap_local_path}")

  s3 = boto3.client("s3", region_name=cfg.region)
  s3.upload_file(
    str(cfg.bootstrap_local_path),
    cfg.s3_bucket,
    cfg.bootstrap_s3_key,
  )
  print(f"[upload] s3://{cfg.s3_bucket}/{cfg.bootstrap_s3_key}")


def _launch_jobs(
  jobs: list[LaunchJob],
  cfg: LaunchConfig,
  *,
  dry_run: bool,
) -> list[str]:
  if not jobs:
    print("[launch] 起動するジョブがありません")
    return []

  if dry_run:
    for job in jobs:
      print(
        f"[dry-run] seed={job.seed} tag={job.tag_name} "
        f"run_name={job.run_name}"
      )
    print("[dry-run] EC2 / S3 にはアクセスしていません。")
    return []

  try:
    import boto3
  except ImportError as exc:
    raise SystemExit("pip install boto3 が必要です") from exc

  ec2 = boto3.client("ec2", region_name=cfg.region)
  ami_id = _resolve_ami_id(ec2, cfg)
  print(f"[launch] region={cfg.region} ami={ami_id} jobs={len(jobs)}")

  instance_ids: list[str] = []
  block_devices = [
    {
      "DeviceName": "/dev/sda1",
      "Ebs": {
        "VolumeSize": cfg.ebs_volume_gb,
        "VolumeType": "gp3",
        "DeleteOnTermination": True,
      },
    }
  ]

  for job in jobs:
    params: dict[str, Any] = {
      "ImageId": ami_id,
      "InstanceType": cfg.instance_type,
      "MinCount": 1,
      "MaxCount": 1,
      "InstanceMarketOptions": {"MarketType": "spot"},
      "IamInstanceProfile": {"Name": cfg.iam_instance_profile},
      "SecurityGroupIds": [cfg.security_group_id],
      "InstanceInitiatedShutdownBehavior": "terminate",
      "BlockDeviceMappings": block_devices,
      "UserData": _user_data_script(job=job, cfg=cfg),
      "TagSpecifications": [
        {
          "ResourceType": "instance",
          "Tags": [
            {"Key": "Name", "Value": job.tag_name},
            {"Key": "SweepId", "Value": job.sweep_id},
            {"Key": "Seed", "Value": str(job.seed)},
          ],
        }
      ],
    }
    if cfg.key_name:
      params["KeyName"] = cfg.key_name

    resp = ec2.run_instances(**params)
    inst = resp["Instances"][0]
    iid = str(inst["InstanceId"])
    instance_ids.append(iid)
    print(f"[launch] started {iid} seed={job.seed} name={job.tag_name}")

  print(
    "[launch] 完了。状態確認例:\n"
    f"  aws ec2 describe-instances --region {cfg.region} "
    f"--instance-ids {' '.join(instance_ids)}\n"
    f"  aws s3 ls s3://{cfg.s3_bucket}/aws-test/ --recursive"
  )
  return instance_ids


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
  p = argparse.ArgumentParser(description=__doc__)
  p.add_argument(
    "--config",
    type=Path,
    default=_DEFAULT_CONFIG,
    help=f"launcher 設定 TOML（既定: {_DEFAULT_CONFIG}）",
  )
  p.add_argument(
    "--parallel",
    type=int,
    default=_DEFAULT_PARALLEL,
    help=f"今回起動するインスタンス数の上限（既定 {_DEFAULT_PARALLEL}）",
  )
  src = p.add_mutually_exclusive_group()
  src.add_argument(
    "--seeds",
    type=str,
    default=None,
    help="学習 seed のカンマ区切り（例: 1,2,3,4）",
  )
  src.add_argument(
    "--sweep",
    type=Path,
    default=None,
    help="sweep YAML（seeds を読み、先頭 --parallel 件を起動）",
  )
  p.add_argument(
    "--sweep-id",
    type=str,
    default="aws_adhoc",
    help="--seeds 使用時の sweep_id プレフィックス（S3 パス・run 名に使用）",
  )
  p.add_argument(
    "--upload-bootstrap",
    action="store_true",
    help="起動前にローカル bootstrap を S3 に upload",
  )
  p.add_argument(
    "--dry-run",
    action="store_true",
    help="EC2 / S3 にアクセスせず、起動予定ジョブとサマリだけ表示",
  )
  p.add_argument(
    "--confirm",
    action="store_true",
    help="本番起動を明示承認（enabled=true と併用必須。無いと EC2 は起動しない）",
  )
  return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
  args = _parse_args(argv)
  cfg = _load_config(args.config.resolve())

  if args.seeds is None and args.sweep is None:
    # 既定: seed 1..parallel
    seeds = tuple(range(1, args.parallel + 1))
    sweep_id = args.sweep_id
    print(f"[plan] --seeds 未指定のため 1..{args.parallel} を使用 sweep_id={sweep_id}")
  elif args.seeds is not None:
    seeds = _parse_seeds(args.seeds)
    sweep_id = args.sweep_id
  else:
    sweep_path = args.sweep.resolve()
    if not sweep_path.is_file():
      raise FileNotFoundError(f"sweep がありません: {sweep_path}")
    sweep_id, seeds = _load_sweep_seeds(sweep_path, shuffle_seed=None)
    print(f"[plan] sweep={sweep_path.name} sweep_id={sweep_id} seeds={list(seeds)}")

  date_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
  jobs = _build_jobs(
    seeds=seeds,
    sweep_id=sweep_id,
    parallel=args.parallel,
    date_stamp=date_stamp,
  )

  if len(seeds) > args.parallel:
    print(
      f"[plan] seed 全 {len(seeds)} 件のうち、先頭 {args.parallel} 件だけ起動します。"
      " 残りは --parallel を増やすか、再度実行してください。"
    )

  print(f"[plan] launch {len(jobs)} instance(s): {[j.seed for j in jobs]}")

  # サマリ表示（dry-run でも課金見込みとアカウント ID を示す）
  account_id = _try_aws_account_id(cfg.region)
  _print_launch_summary(
    cfg=cfg,
    jobs=jobs,
    dry_run=args.dry_run,
    upload_bootstrap=args.upload_bootstrap,
    aws_account_id=account_id,
    ami_id=cfg.ami_id or None,
  )

  if args.dry_run:
    _launch_jobs(jobs, cfg, dry_run=True)
    return

  _guard_real_launch(cfg=cfg, confirm=args.confirm)

  # confirm 後に再度アカウントを表示（本番直前）
  account_id = _try_aws_account_id(cfg.region)
  if account_id:
    print(f"[confirm] AWS アカウント {account_id} で起動します。")

  if args.upload_bootstrap:
    _upload_bootstrap(cfg)

  _launch_jobs(jobs, cfg, dry_run=False)


if __name__ == "__main__":
  main()
