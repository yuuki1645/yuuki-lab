#pragma once

/**
 * model_2200 の方策。入力 38、隠れ 128 と 64、ELU、出力 10。
 * 重みは policy_weights.hpp。スタックには置かない。
 * 制御タスクだけが呼ぶ。
 */

/** 正規化してから 3 層。出力は学習の生アクション（0.25 を掛ける前）。 */
void policyForward(const float obs[38], float action[10]);
