/**
 * 観測を組んで方策を回し、画面の度へ戻す。
 *
 * 観測の順は学習の PolicyCfg と同じ。
 *   0..9   関節角 [rad]。直立が 0。方策の並びは左股ロールから。
 *   10..12 重力。体座標。直立の z は約 -1。
 *   13..15 角速度 [rad/s]。同じ体座標。
 *   16..23 足裏 [kg]。左の四隅、右の四隅。各足はつま先左、つま先右、かかと左、かかと右。
 *   24..25 位相の sin, cos。周期 2 秒。指令が 0 でも時計は進む。
 *   26..27 前進指令 [m/s] とヨー [rad/s]。横は入れない。ヨーは常に 0。
 *   28..37 直前の生アクション。0.25 を掛ける前。
 *
 * 度とラジアンの対応は robot_description/hub_link.py。
 * RDS51150 の直立は 135°、SM105BL の直立は 0°。0° を 135° の式に入れない。
 * 足の kg は atom-rt/tools/lib/df9_force.py と同じ曲線。そのあと 0.02 kg 未満を 0 にする。
 */

#include "walk_policy.hpp"

#include "bmi270_waist.hpp"
#include "policy_net.hpp"

#include <Arduino.h>
#include <math.h>

static constexpr float kPi = 3.14159265f;
static constexpr float kDegToRad = kPi / 180.0f;
static constexpr float kRadToDeg = 180.0f / kPi;

static constexpr float kRdsNeutralDeg = 135.0f;
static constexpr float kSmsNeutralDeg = 0.0f;
static constexpr float kActionScale = 0.25f;
static constexpr float kPeriodS = 2.0f;
static constexpr float kVxMax = 0.2f;
static constexpr float kDeadzoneKg = 0.02f;
static constexpr float kMaxKg = 2.0f;

// 直立に見えるまでネットを回さない。約 20° より傾いていると外す。
static constexpr float kUprightXy = 0.35f;
static constexpr float kUprightZ = -0.80f;

static constexpr float kRdsMinDeg = 40.0f;
static constexpr float kRdsMaxDeg = 230.0f;
static constexpr float kKneeMinDeg = -30.0f;
static constexpr float kKneeMaxDeg = 150.0f;
static constexpr float kAnkleMinDeg = -60.0f;
static constexpr float kAnkleMaxDeg = 60.0f;

/**
 * 方策の関節 0..9 が指すファームの論理軸。
 * 方策は左股ロール、右股ロール、左股ピッチ、右股ピッチ、左ひざ、右ひざ、
 * 左かかとピッチ、右かかとピッチ、左かかとロール、右かかとロール。
 * ファームは右 0..4、左 5..9。
 */
static constexpr int kFwForPolicy[kCoreJoints] = {5, 0, 6, 1, 7, 2, 8, 3, 9, 4};

/** CAN の四隅（つま先左、つま先右、かかと右、かかと左）から、方策の並びへの添字。 */
static constexpr int kCornerFromMv[4] = {0, 1, 3, 2};

static constexpr float kForceRTable[][2] = {
    {0.20f, 11200.0f}, {0.40f, 6070.0f}, {0.60f, 4310.0f}, {0.80f, 3430.0f},
    {1.00f, 2970.0f},  {1.20f, 2670.0f}, {1.40f, 2480.0f}, {1.60f, 2300.0f},
    {1.80f, 2190.0f},  {2.00f, 2080.0f},
};

static portMUX_TYPE gPolicyLock = portMUX_INITIALIZER_UNLOCKED;
static bool gReqOn = false;
static float gReqVx = 0.0f;

static bool gArmed = false;
static float gPhase = 0.0f;
static uint32_t gPhaseUs = 0;
static float gLastAction[kCoreJoints] = {};

static PolicyView gView{};
static uint8_t gStatusDiv = 0;
static volatile uint8_t gStatusReady = 0;

static bool isSms(int fw) {
    const int axis = fw % 5;
    return axis == kAxisKnee || axis == kAxisAnklePitch;
}

static float clampRange(float deg, float lo, float hi) {
    if (deg < lo) {
        return lo;
    }
    if (deg > hi) {
        return hi;
    }
    return deg;
}

/** main.cpp の clampMove / clampSms と同じ範囲。 */
static float clampJointDeg(int fw, float deg) {
    if (!isSms(fw)) {
        return clampRange(deg, kRdsMinDeg, kRdsMaxDeg);
    }
    if ((fw % 5) == kAxisKnee) {
        return clampRange(deg, kKneeMinDeg, kKneeMaxDeg);
    }
    return clampRange(deg, kAnkleMinDeg, kAnkleMaxDeg);
}

static float degToPolicyRad(int fw, float deg) {
    const float neutral = isSms(fw) ? kSmsNeutralDeg : kRdsNeutralDeg;
    return (deg - neutral) * kDegToRad;
}

static float policyRadToDeg(int fw, float rad) {
    const float neutral = isSms(fw) ? kSmsNeutralDeg : kRdsNeutralDeg;
    return neutral + rad * kRadToDeg;
}

static void fillNeutral(float cmd[kCoreJoints]) {
    for (int fw = 0; fw < kCoreJoints; ++fw) {
        cmd[fw] = isSms(fw) ? kSmsNeutralDeg : kRdsNeutralDeg;
    }
}

static float clampf(float value, float lo, float hi) {
    if (value < lo) {
        return lo;
    }
    if (value > hi) {
        return hi;
    }
    return value;
}

/** df9_force.py の voltage_to_force_kg。抵抗の対数で区間を分ける。 */
static float voltageToKg(float voltage) {
    float rs;
    if (voltage < 0.02f) {
        rs = 10000000.0f;
    } else {
        rs = 10000.0f * (3.3f / voltage - 1.0f);
        if (rs < 1.0f) {
            rs = 1.0f;
        }
    }
    if (rs >= 1000000.0f) {
        return 0.0f;
    }
    const int n = static_cast<int>(sizeof(kForceRTable) / sizeof(kForceRTable[0]));
    if (rs >= kForceRTable[0][1]) {
        const float r0 = 1000000.0f;
        const float f0 = 0.005f;
        const float f1 = kForceRTable[0][0];
        const float r1 = kForceRTable[0][1];
        const float t = (logf(rs) - logf(r0)) / (logf(r1) - logf(r0));
        return clampf(f0 * expf(t * (logf(f1) - logf(f0))), 0.0f, kMaxKg);
    }
    if (rs <= kForceRTable[n - 1][1]) {
        return kMaxKg;
    }
    for (int i = 0; i < n - 1; ++i) {
        const float f1 = kForceRTable[i][0];
        const float r1 = kForceRTable[i][1];
        const float f2 = kForceRTable[i + 1][0];
        const float r2 = kForceRTable[i + 1][1];
        if (r1 >= rs && rs >= r2) {
            const float t = (logf(rs) - logf(r1)) / (logf(r2) - logf(r1));
            const float log_f = logf(f1) + t * (logf(f2) - logf(f1));
            return clampf(expf(log_f), 0.0f, kMaxKg);
        }
    }
    return 0.0f;
}

static bool footKg(const PolicyFoot& foot, float out[4]) {
    if (!foot.ok || (foot.mask & 0x0F) != 0x0F) {
        return false;
    }
    for (int corner = 0; corner < 4; ++corner) {
        const int mv_index = kCornerFromMv[corner];
        float kg = voltageToKg(static_cast<float>(foot.mv[mv_index]) / 1000.0f);
        if (kg < kDeadzoneKg) {
            kg = 0.0f;
        }
        out[corner] = kg;
    }
    return true;
}

static bool jointsOk(const PolicySense& sense) {
    if (sense.corr_deg == nullptr || sense.as_ok == nullptr || sense.map_ok == nullptr) {
        return false;
    }
    for (int fw = 0; fw < kCoreJoints; ++fw) {
        // 欠測の補正角は NaN。NaN は自分自身と等しくない。
        if (!sense.as_ok[fw] || sense.corr_deg[fw] != sense.corr_deg[fw]) {
            return false;
        }
        // SM105 はサーボの現在角。校正マップは RDS だけが要る。
        if (!isSms(fw) && !sense.map_ok[fw]) {
            return false;
        }
    }
    return true;
}

static void publish(const PolicyStep& step, bool enable) {
    portENTER_CRITICAL(&gPolicyLock);
    gView.enable = enable ? 1 : 0;
    gView.ran = step.ran ? 1 : 0;
    gView.reason = step.reason;
    for (int i = 0; i < 3; ++i) {
        gView.gravity[i] = step.gravity[i];
        gView.gyro_rad[i] = step.gyro_rad[i];
    }
    gView.vx_mps = step.vx_mps;
    portEXIT_CRITICAL(&gPolicyLock);
    // 入り始めと、そのあと 6 周期に 1 回。テレメトリを毎周期ふやかさない。
    if (enable) {
        const uint8_t div = gStatusDiv;
        gStatusDiv = static_cast<uint8_t>((div + 1) % 6);
        if (div == 0) {
            gStatusReady = 1;
        }
    }
}

static void hold(PolicyStep& out, uint8_t reason) {
    out.write_cmd = true;
    out.ran = false;
    out.reason = reason;
    fillNeutral(out.cmd_deg);
}

static bool looksUpright(const float gravity[3]) {
    return fabsf(gravity[0]) < kUprightXy && fabsf(gravity[1]) < kUprightXy && gravity[2] < kUprightZ;
}

static void projectGravity(const float specific_force_g[3], float gravity[3]) {
    const float n2 = specific_force_g[0] * specific_force_g[0] + specific_force_g[1] * specific_force_g[1] +
                     specific_force_g[2] * specific_force_g[2];
    const float n = sqrtf(n2);
    // ほぼ 0 は未初期化。歩行中の加速度はここでは落とさない。
    if (n < 0.2f) {
        gravity[0] = 0.0f;
        gravity[1] = 0.0f;
        gravity[2] = 0.0f;
        return;
    }
    for (int i = 0; i < 3; ++i) {
        gravity[i] = -specific_force_g[i] / n;
    }
}

void policyRequest(bool enable, float vx_mps) {
    float vx = 0.0f;
    if (enable) {
        vx = clampf(vx_mps, 0.0f, kVxMax);
    }
    portENTER_CRITICAL(&gPolicyLock);
    const bool rising = enable && !gReqOn;
    portEXIT_CRITICAL(&gPolicyLock);
    if (rising) {
        // gReqOn を立てる前に戻す。制御タスクはまだこの周期へ入らない。
        gArmed = false;
        gPhase = 0.0f;
        gPhaseUs = 0;
        gStatusDiv = 0;
        for (int i = 0; i < kCoreJoints; ++i) {
            gLastAction[i] = 0.0f;
        }
    }
    portENTER_CRITICAL(&gPolicyLock);
    gReqOn = enable;
    gReqVx = vx;
    if (!enable) {
        gView.enable = 0;
        gView.ran = 0;
        gView.reason = kPolicyReasonOff;
        gView.vx_mps = 0.0f;
        // 切ったことを画面へ 1 回出す。入っているあいだの定期送信とは別に出す。
        gStatusReady = 1;
    }
    portEXIT_CRITICAL(&gPolicyLock);
}

bool policyRequested() {
    portENTER_CRITICAL(&gPolicyLock);
    const bool on = gReqOn;
    portEXIT_CRITICAL(&gPolicyLock);
    return on;
}

bool policyTakeStatus(PolicyView& out) {
    if (!gStatusReady) {
        return false;
    }
    gStatusReady = 0;
    portENTER_CRITICAL(&gPolicyLock);
    out = gView;
    portEXIT_CRITICAL(&gPolicyLock);
    return true;
}

void policyStep(const PolicySense& sense, PolicyStep& out) {
    const uint32_t t0 = micros();
    out = {};
    out.elapsed_us = 0;

    bool enable = false;
    float vx = 0.0f;
    portENTER_CRITICAL(&gPolicyLock);
    enable = gReqOn;
    vx = gReqVx;
    portEXIT_CRITICAL(&gPolicyLock);
    out.vx_mps = vx;

    if (!enable) {
        out.reason = kPolicyReasonOff;
        out.elapsed_us = micros() - t0;
        publish(out, false);
        return;
    }
    if (sense.fault) {
        out.reason = kPolicyReasonFault;
        out.elapsed_us = micros() - t0;
        publish(out, true);
        return;
    }

    float specific[3] = {};
    float gyro[3] = {};
    const bool imu_ok = bmi270Read(specific, gyro);
    if (imu_ok) {
        projectGravity(specific, out.gravity);
        for (int i = 0; i < 3; ++i) {
            out.gyro_rad[i] = gyro[i];
        }
    }

    float left_kg[4] = {};
    float right_kg[4] = {};
    const bool feet_ok = sense.foot != nullptr && footKg(sense.foot[1], left_kg) && footKg(sense.foot[0], right_kg);
    const bool gravity_ok = imu_ok && !(out.gravity[0] == 0.0f && out.gravity[1] == 0.0f && out.gravity[2] == 0.0f);
    if (!jointsOk(sense)) {
        hold(out, kPolicyReasonJoint);
    } else if (!feet_ok) {
        hold(out, kPolicyReasonFoot);
    } else if (!gravity_ok) {
        hold(out, kPolicyReasonImu);
    } else if (!gArmed && !looksUpright(out.gravity)) {
        hold(out, kPolicyReasonNotUpright);
    } else {
        if (!gArmed) {
            gArmed = true;
            gPhase = 0.0f;
            gPhaseUs = micros();
            for (int i = 0; i < kCoreJoints; ++i) {
                gLastAction[i] = 0.0f;
            }
        }
        const uint32_t now = micros();
        const float dt = static_cast<float>(now - gPhaseUs) * 1.0e-6f;
        gPhaseUs = now;
        gPhase = fmodf(gPhase + (2.0f * kPi * dt / kPeriodS), 2.0f * kPi);
        if (gPhase < 0.0f) {
            gPhase += 2.0f * kPi;
        }

        float obs[38];
        for (int p = 0; p < kCoreJoints; ++p) {
            obs[p] = degToPolicyRad(kFwForPolicy[p], sense.corr_deg[kFwForPolicy[p]]);
        }
        obs[10] = out.gravity[0];
        obs[11] = out.gravity[1];
        obs[12] = out.gravity[2];
        obs[13] = out.gyro_rad[0];
        obs[14] = out.gyro_rad[1];
        obs[15] = out.gyro_rad[2];
        for (int i = 0; i < 4; ++i) {
            obs[16 + i] = left_kg[i];
            obs[20 + i] = right_kg[i];
        }
        obs[24] = sinf(gPhase);
        obs[25] = cosf(gPhase);
        obs[26] = vx;
        obs[27] = 0.0f;
        for (int i = 0; i < kCoreJoints; ++i) {
            obs[28 + i] = gLastAction[i];
        }

        float action[kCoreJoints];
        policyForward(obs, action);
        for (int p = 0; p < kCoreJoints; ++p) {
            gLastAction[p] = action[p];
            const int fw = kFwForPolicy[p];
            out.cmd_deg[fw] = clampJointDeg(fw, policyRadToDeg(fw, action[p] * kActionScale));
        }
        out.write_cmd = true;
        out.ran = true;
        out.reason = kPolicyReasonRan;
    }

    out.elapsed_us = micros() - t0;
    publish(out, true);
}
