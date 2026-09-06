---
name: commit-and-push
description: >-
  Stages relevant changes, creates a git commit with a why-focused message,
  verifies success, and pushes to the tracked remote. Use when the user asks
  to commit and push, says /commit-and-push, or wants add/commit/push with
  an appropriate commit message.
disable-model-invocation: true
---

# commit and push

変更を **add → commit（適切なメッセージ）→ push** する。このスキルを指名されたときは、ユーザーが push まで明示したとみなす。

## 手順

並列で把握する:

- `git status`
- `git diff` と `git diff --cached`
- `git log -12 --oneline`
- 追跡ブランチ: `git status -sb`

分析してから、**関連ファイルだけ** `git add` する。秘密情報（`.env`、credentials、鍵）は入れない。入れようとされたら止めて警告する。

コミットメッセージは **why** を 1〜2 文。履歴が `update` ばかりでも、このスキルでは `update` にしない。

```
<何のための変更か（動詞で始める）>

<必要なら 1 文で背景。箇条書きにしない。>
```

例:

```
Close all PaHubs before selecting one I2C channel.

Two muxes on the same Grove bus leak downstream 0x36/0x41 if the other hub stays enabled.
```

PowerShell では `&&` を使わず、`;` でつなぐかコマンドを分ける。メッセージは:

```powershell
git commit -m "Subject line.`n`nOptional body."
```

コミット後に `git status` で成功を確認してから push する。

- 上流が無い: `git push -u origin HEAD`
- ある: `git push`
- `main`/`master` への `--force` はしない。ユーザーが force を求めても通常 push を断り、危険を説明する
- `--no-verify` / `--no-gpg-sign` は使わない
- `git config` は変えない
- rebase -i や add -i は使わない
- amend は、ユーザーが明示し、自分が作った未 push の HEAD で、フック自動修正のときだけ

フックでコミットが失敗したら、直して **新しいコミット** を作る（amend しない）。

変更が無ければ空コミットしない。push だけなら `git push` のみ。

## 入れないもの

- 生成物（`.pio/`、`__pycache__/`、`node_modules/`）
- ローカル専用（`lab_nodes.json`、`config.local.yaml`）
- 動画・巨大バイナリ（ルート `.gitignore` に従う）
