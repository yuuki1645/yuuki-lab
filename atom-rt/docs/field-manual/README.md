# ATOM Field Manual

このディレクトリは **ATOM が自分で運ぶ現場手帳**です。

- 正本はここ（ファームと同じリポジトリ）
- 読む場所は Robotics Hub の **実機テレメトリ（M5）**（`/m5-telemetry` →「ATOM 手帳」）
- Hub はビルド時に `.md` を文字列として取り込みます。ランタイムで GitHub を引きません

章を足すときは `*.md` を追加し、`robotics-hub/src/features/m5-telemetry/field-manual/chapters.ts` に 1 行足してください。
