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

// サーボの最高速度。これを超える角の変化は、センサの飛びとみなす。
static constexpr float kRdsSpeedRad = 5.0f;
static constexpr float kSmsSpeedRad = 6.3f;
// 前進 0 のとき、直立からこの角を超えた状態が続くとネットを止める。約 20°。
static constexpr float kEnvelopeRad = 0.35f;
static constexpr int kEnvelopeCycles = 15;
// 直立へ戻しているあいだ、計測がこの角だけさらに外へ行く周期が続くと目標を固定する。
static constexpr int kDivergeCycles = 8;
static constexpr float kDivergeRad = 0.02f;
// 直近 8 周期の標準偏差がこれ以上なら、揺れ。ネットは回し、分布の平均からは外す。
static constexpr float kShakeStdRad = 0.08f;
static constexpr int kHistLen = 8;
static constexpr float kVxStand = 0.02f;
static constexpr float kFootBearingKg = 1.0f;
static constexpr uint16_t kAgeUnknown = 65535;
static constexpr float kDtDefault = 1.0f / 30.0f;
static constexpr float kDtMax = 0.1f;

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

// 飛び判定の直前値と、揺れ判定の窓。有効な角が入った軸だけ true。
static float gLastMeasRad[kCoreJoints];
static uint8_t gHaveMeas[kCoreJoints];
static float gHist[kCoreJoints][kHistLen];
static uint8_t gHistN[kCoreJoints];
static uint8_t gHistI[kCoreJoints];
// 直前に出した目標。最初の 1 回は計測角から速度制限を始める。
static float gLastCmdDeg[kCoreJoints];
static uint8_t gHaveCmd = 0;
static int gOutsideCycles = 0;
static int gDivergeCycles = 0;
static float gPrevSpanRad = 0.0f;
static uint8_t gFollowNet = 1;
static uint8_t gFrozen = 0;
static UsbPolicyTrace gTrace{};
static volatile uint8_t gTraceReady = 0;
static uint32_t gTraceSeq = 0;

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
    gView.safety = step.safety;
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

static float maxSpeedRad(int fw) {
    return isSms(fw) ? kSmsSpeedRad : kRdsSpeedRad;
}

/** 直前の目標から、この周期で出せる角まで近づける。制限したら true。 */
static bool slewDeg(int fw, float from_deg, float to_deg, float dt, float* out_deg) {
    const float cap = maxSpeedRad(fw) * dt * kRadToDeg;
    const float delta = to_deg - from_deg;
    if (delta > cap) {
        *out_deg = from_deg + cap;
        return true;
    }
    if (delta < -cap) {
        *out_deg = from_deg - cap;
        return true;
    }
    *out_deg = to_deg;
    return false;
}

static void pushHist(int policy_index, float rad) {
    gHist[policy_index][gHistI[policy_index]] = rad;
    gHistI[policy_index] = static_cast<uint8_t>((gHistI[policy_index] + 1) % kHistLen);
    if (gHistN[policy_index] < kHistLen) {
        gHistN[policy_index] = static_cast<uint8_t>(gHistN[policy_index] + 1);
    }
}

static bool histShaking(int policy_index) {
    if (gHistN[policy_index] < kHistLen) {
        return false;
    }
    float sum = 0.0f;
    for (int i = 0; i < kHistLen; ++i) {
        sum += gHist[policy_index][i];
    }
    const float mean = sum / static_cast<float>(kHistLen);
    float acc = 0.0f;
    for (int i = 0; i < kHistLen; ++i) {
        const float d = gHist[policy_index][i] - mean;
        acc += d * d;
    }
    return sqrtf(acc / static_cast<float>(kHistLen)) > kShakeStdRad;
}

static void commitTrace(const UsbPolicyTrace& trace) {
    portENTER_CRITICAL(&gPolicyLock);
    gTrace = trace;
    gTraceReady = 1;
    portEXIT_CRITICAL(&gPolicyLock);
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
        gFollowNet = 1;
        gFrozen = 0;
        gOutsideCycles = 0;
        gDivergeCycles = 0;
        gPrevSpanRad = 0.0f;
        gHaveCmd = 0;
        for (int i = 0; i < kCoreJoints; ++i) {
            gLastAction[i] = 0.0f;
            gHaveMeas[i] = 0;
            gHistN[i] = 0;
            gHistI[i] = 0;
        }
    }
    portENTER_CRITICAL(&gPolicyLock);
    gReqOn = enable;
    gReqVx = vx;
    if (!enable) {
        gView.enable = 0;
        gView.ran = 0;
        gView.reason = kPolicyReasonOff;
        gView.safety = kPolicySafetyNone;
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

bool policyTakeTrace(UsbPolicyTrace& out) {
    portENTER_CRITICAL(&gPolicyLock);
    if (!gTraceReady) {
        portEXIT_CRITICAL(&gPolicyLock);
        return false;
    }
    gTraceReady = 0;
    out = gTrace;
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

    // 周期の長さ。センサの飛びと、目標の速度制限が同じ dt を使う。
    float dt = kDtDefault;
    if (sense.period_us >= 1000 && sense.period_us <= static_cast<uint32_t>(kDtMax * 1.0e6f)) {
        dt = static_cast<float>(sense.period_us) * 1.0e-6f;
    }

    float meas_rad[kCoreJoints];
    uint8_t joint_flag[kCoreJoints];
    bool any_bad = false;
    for (int p = 0; p < kCoreJoints; ++p) {
        const int fw = kFwForPolicy[p];
        meas_rad[p] = NAN;
        joint_flag[p] = kJointFlagMissing;
        const bool present = sense.corr_deg != nullptr && sense.as_ok != nullptr && sense.as_ok[fw] &&
                             sense.corr_deg[fw] == sense.corr_deg[fw] && (isSms(fw) || (sense.map_ok != nullptr && sense.map_ok[fw]));
        if (!present) {
            any_bad = true;
            continue;
        }
        const float rad = degToPolicyRad(fw, sense.corr_deg[fw]);
        meas_rad[p] = rad;
        if (gHaveMeas[p]) {
            const float step = fabsf(rad - gLastMeasRad[p]);
            if (step > maxSpeedRad(fw) * dt) {
                joint_flag[p] = kJointFlagJump;
                any_bad = true;
                gLastMeasRad[p] = rad;
                continue;
            }
        }
        gLastMeasRad[p] = rad;
        gHaveMeas[p] = 1;
        pushHist(p, rad);
        joint_flag[p] = histShaking(p) ? kJointFlagShake : kJointFlagValid;
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
    const bool gravity_ok = imu_ok && !(out.gravity[0] == 0.0f && out.gravity[1] == 0.0f && out.gravity[2] == 0.0f);

    float left_kg[4] = {};
    float right_kg[4] = {};
    const bool feet_ok = sense.foot != nullptr && footKg(sense.foot[1], left_kg) && footKg(sense.foot[0], right_kg);
    float foot_sum = 0.0f;
    if (feet_ok) {
        for (int i = 0; i < 4; ++i) {
            foot_sum += left_kg[i] + right_kg[i];
        }
    }

    float obs[kPolicyObs];
    for (int i = 0; i < kPolicyObs; ++i) {
        obs[i] = NAN;
    }
    for (int p = 0; p < kCoreJoints; ++p) {
        obs[p] = meas_rad[p];
    }
    if (gravity_ok) {
        obs[10] = out.gravity[0];
        obs[11] = out.gravity[1];
        obs[12] = out.gravity[2];
        obs[13] = out.gyro_rad[0];
        obs[14] = out.gyro_rad[1];
        obs[15] = out.gyro_rad[2];
    }
    if (feet_ok) {
        for (int i = 0; i < 4; ++i) {
            obs[16 + i] = left_kg[i];
            obs[20 + i] = right_kg[i];
        }
    }
    obs[26] = enable ? vx : 0.0f;
    obs[27] = 0.0f;
    for (int i = 0; i < kCoreJoints; ++i) {
        obs[28 + i] = enable ? gLastAction[i] : 0.0f;
    }

    float action[kCoreJoints];
    for (int i = 0; i < kCoreJoints; ++i) {
        action[i] = NAN;
    }
    float desired[kCoreJoints];
    fillNeutral(desired);

    const bool can_run = enable && !sense.fault && !any_bad && feet_ok && gravity_ok && gFollowNet && !gFrozen &&
                         (gArmed || looksUpright(out.gravity));
    if (can_run) {
        if (!gArmed) {
            gArmed = true;
            gPhase = 0.0f;
            gPhaseUs = micros();
            for (int i = 0; i < kCoreJoints; ++i) {
                gLastAction[i] = 0.0f;
                obs[28 + i] = 0.0f;
            }
        }
        const uint32_t now = micros();
        const float phase_dt = static_cast<float>(now - gPhaseUs) * 1.0e-6f;
        gPhaseUs = now;
        gPhase = fmodf(gPhase + (2.0f * kPi * phase_dt / kPeriodS), 2.0f * kPi);
        if (gPhase < 0.0f) {
            gPhase += 2.0f * kPi;
        }
        obs[24] = sinf(gPhase);
        obs[25] = cosf(gPhase);
        policyForward(obs, action);
        for (int p = 0; p < kCoreJoints; ++p) {
            // ここまで来る軸は有効か揺れだけ。欠測と飛びの周期は、ネットを呼ばない。
            gLastAction[p] = action[p];
            const int fw = kFwForPolicy[p];
            desired[fw] = clampJointDeg(fw, policyRadToDeg(fw, action[p] * kActionScale));
        }
        out.ran = true;
        out.reason = kPolicyReasonRan;
    } else if (!enable) {
        out.reason = kPolicyReasonOff;
        obs[24] = 0.0f;
        obs[25] = 1.0f;
    } else if (sense.fault) {
        out.reason = kPolicyReasonFault;
    } else if (any_bad) {
        out.reason = kPolicyReasonJoint;
    } else if (!feet_ok) {
        out.reason = kPolicyReasonFoot;
    } else if (!gravity_ok) {
        out.reason = kPolicyReasonImu;
    } else if (gFrozen) {
        out.reason = kPolicyReasonFrozen;
    } else if (!gFollowNet) {
        out.reason = kPolicyReasonEnvelope;
    } else {
        out.reason = kPolicyReasonNotUpright;
    }

    // 前進 0 で、目標か計測が包絡の外に居続ける。ネットは止め、直立へ戻す。
    if (enable && !sense.fault && out.ran && vx <= kVxStand) {
        bool outside = false;
        for (int p = 0; p < kCoreJoints; ++p) {
            const int fw = kFwForPolicy[p];
            if (fabsf(degToPolicyRad(fw, desired[fw])) > kEnvelopeRad) {
                outside = true;
            }
            if (joint_flag[p] != kJointFlagMissing && joint_flag[p] != kJointFlagJump && fabsf(meas_rad[p]) > kEnvelopeRad) {
                outside = true;
            }
        }
        if (outside) {
            gOutsideCycles += 1;
        } else {
            gOutsideCycles = 0;
        }
        if (gOutsideCycles >= kEnvelopeCycles) {
            gFollowNet = 0;
            out.ran = false;
            out.reason = kPolicyReasonEnvelope;
            fillNeutral(desired);
        }
    } else if (!enable) {
        gOutsideCycles = 0;
    }

    // 戻すまでのあいだも、直立指令では包絡の外へ目標を出さない。
    bool capped = false;
    if (enable && !sense.fault && vx <= kVxStand && gFollowNet && !gFrozen) {
        for (int fw = 0; fw < kCoreJoints; ++fw) {
            float rad = degToPolicyRad(fw, desired[fw]);
            if (rad > kEnvelopeRad) {
                rad = kEnvelopeRad;
                capped = true;
            } else if (rad < -kEnvelopeRad) {
                rad = -kEnvelopeRad;
                capped = true;
            }
            desired[fw] = clampJointDeg(fw, policyRadToDeg(fw, rad));
        }
    }

    uint8_t safety = kPolicySafetyNone;
    if (enable && !sense.fault) {
        if (gFrozen) {
            for (int fw = 0; fw < kCoreJoints; ++fw) {
                out.cmd_deg[fw] = gHaveCmd ? gLastCmdDeg[fw] : desired[fw];
            }
            safety = kPolicySafetyFreeze;
            out.reason = kPolicyReasonFrozen;
            out.ran = false;
            out.write_cmd = true;
        } else {
            bool limited = false;
            for (int fw = 0; fw < kCoreJoints; ++fw) {
                float from = desired[fw];
                if (gHaveCmd) {
                    from = gLastCmdDeg[fw];
                } else if (sense.corr_deg != nullptr && sense.corr_deg[fw] == sense.corr_deg[fw]) {
                    from = sense.corr_deg[fw];
                }
                float next = desired[fw];
                if (slewDeg(fw, from, desired[fw], dt, &next)) {
                    limited = true;
                }
                out.cmd_deg[fw] = next;
            }
            // 戻しているあいだ、計測の最大偏差が増え続けるなら、その場で目標を止める。
            if (!gFollowNet) {
                float span = 0.0f;
                for (int p = 0; p < kCoreJoints; ++p) {
                    if (joint_flag[p] == kJointFlagMissing || joint_flag[p] == kJointFlagJump) {
                        continue;
                    }
                    const float mag = fabsf(meas_rad[p]);
                    if (mag > span) {
                        span = mag;
                    }
                }
                if (span > gPrevSpanRad + kDivergeRad) {
                    gDivergeCycles += 1;
                } else {
                    gDivergeCycles = 0;
                }
                gPrevSpanRad = span;
                if (gDivergeCycles >= kDivergeCycles && gHaveCmd) {
                    gFrozen = 1;
                    for (int fw = 0; fw < kCoreJoints; ++fw) {
                        out.cmd_deg[fw] = gLastCmdDeg[fw];
                    }
                    safety = kPolicySafetyFreeze;
                    out.reason = kPolicyReasonFrozen;
                    out.ran = false;
                }
            }
            if (safety != kPolicySafetyFreeze) {
                if (!gFollowNet) {
                    safety = kPolicySafetyEnvelope;
                } else if (limited || capped) {
                    safety = kPolicySafetyRate;
                }
            }
            for (int fw = 0; fw < kCoreJoints; ++fw) {
                gLastCmdDeg[fw] = out.cmd_deg[fw];
            }
            gHaveCmd = 1;
            out.write_cmd = true;
        }
    }

    bool sensor_ok = gravity_ok;
    for (int p = 0; p < kCoreJoints; ++p) {
        if (joint_flag[p] == kJointFlagMissing || joint_flag[p] == kJointFlagJump) {
            sensor_ok = false;
        }
    }
    const uint8_t dist_ok = (safety == kPolicySafetyNone && sensor_ok) ? 1 : 0;
    out.safety = safety;
    out.elapsed_us = micros() - t0;

    UsbPolicyTrace trace{};
    trace.seq = gTraceSeq++;
    trace.t_period_us = sense.period_us;
    trace.t_sense_us = sense.sense_us;
    trace.t_policy_us = out.elapsed_us;
    trace.overrun = sense.overrun;
    trace.reason = out.reason;
    trace.safety = safety;
    trace.foot_bearing = (feet_ok && foot_sum >= kFootBearingKg) ? 1 : 0;
    trace.dist_ok = dist_ok;
    for (int p = 0; p < kCoreJoints; ++p) {
        trace.joint_flag[p] = joint_flag[p];
        const int fw = kFwForPolicy[p];
        trace.age_ms[p] = (sense.age_joint_ms != nullptr) ? sense.age_joint_ms[fw] : kAgeUnknown;
        trace.obs[p] = obs[p];
        trace.action[p] = action[p];
        const float cmd_deg = out.write_cmd ? out.cmd_deg[fw] : (sense.cmd_deg != nullptr ? sense.cmd_deg[fw] : NAN);
        trace.cmd_rad[p] = cmd_deg == cmd_deg ? degToPolicyRad(fw, cmd_deg) : NAN;
    }
    for (int i = 10; i < kPolicyObs; ++i) {
        trace.obs[i] = obs[i];
    }
    trace.age_ms[kCoreJoints] = sense.age_imu_ms == 0 && !gravity_ok ? kAgeUnknown : sense.age_imu_ms;
    if (!gravity_ok) {
        trace.age_ms[kCoreJoints] = kAgeUnknown;
    }
    trace.age_ms[kCoreJoints + 1] = feet_ok ? sense.age_foot_ms : kAgeUnknown;
    commitTrace(trace);
    publish(out, enable);
}
