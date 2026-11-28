/**
 * 方策の順伝播。ガウス分布の乱数は足さない。学習の推論と同じく平均だけを返す。
 *
 * 隠れ層の作業バッファは静的領域。制御タスクのスタック（約 12 KB）には置かない。
 * この関数は制御タスク以外から呼ばない。
 */

#include "policy_net.hpp"

#include "policy_weights.hpp"

#include <math.h>

static_assert(kPolicyObs == 38, "観測の長さ");
static_assert(kPolicyHidden1 == 128, "第 1 隠れ層");
static_assert(kPolicyHidden2 == 64, "第 2 隠れ層");
static_assert(kPolicyAct == 10, "関節の出力");

/** y = W x + b。elu のとき、正はそのまま、負は exp(x) - 1。W は (出力, 入力)。 */
static void linear(const float* weight, const float* bias, const float* x, float* y, int outputs,
                    int inputs, bool elu) {
    for (int o = 0; o < outputs; ++o) {
        float sum = bias[o];
        const float* row = weight + (o * inputs);
        for (int i = 0; i < inputs; ++i) {
            sum += row[i] * x[i];
        }
        if (elu) {
            sum = sum > 0.0f ? sum : expf(sum) - 1.0f;
        }
        y[o] = sum;
    }
}

void policyForward(const float obs[38], float action[10]) {
    static float norm[kPolicyObs];
    static float h1[kPolicyHidden1];
    static float h2[kPolicyHidden2];

    for (int i = 0; i < kPolicyObs; ++i) {
        norm[i] = (obs[i] - kPolicyObsMean[i]) / (kPolicyObsStd[i] + kPolicyNormEps);
    }
    linear(kPolicyW0, kPolicyB0, norm, h1, kPolicyHidden1, kPolicyObs, true);
    linear(kPolicyW1, kPolicyB1, h1, h2, kPolicyHidden2, kPolicyHidden1, true);
    linear(kPolicyW2, kPolicyB2, h2, action, kPolicyAct, kPolicyHidden2, false);
}
