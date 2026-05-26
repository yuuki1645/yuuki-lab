---
name: test-skill-2
description: CursorのSkill機能をテストする
disable-model-invocation: true
---

# Test Skill 1

## Instructions
1. 指定された実験番号のexpが存在するか、mujoco-sim/mujoco_rl_sim/experimentsのディレクトリの中をチェックする。既に指定された実験番号のexpフォルダが存在した場合、エラーでこのスキルを終了する。実験番号が指定されなかった場合、実験番号を確認質問する。

1. 指定された実験番号で「強化学習実験000」（000の部分は実験番号、3桁0埋め）のタイトルのイシューを作成する。イシューを作成する際のdescriptionは「[Cursor created]」にする。

1. mujoco-sim/mujoco_rl_sim/experimentsディレクトリの中にexp_000...（000の部分は実験番号、3桁0埋め）という名称の実験ディレクトリを作成する

## 進捗表示
- 実行開始時: Instructions の各手順を Todo 一覧にする
- 各手順の完了直後: 該当 Todo を completed にする
- 手順が1つだけでも同様に行う

## 注意事項
- スキルがイシューにコメントをする時は、コメント冒頭に「[Cursor AI]」を追加する
