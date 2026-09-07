#pragma once

/**
 * DF9-40@2kg の抵抗→力換算（スレーブ LED 用の概算）。
 *
 * 正確な表示は PC 側 tools/df9_force.py が正本。
 * データシート Data reference sheet（2kg 列）の log-log 補間。
 *
 * 回路（センサー上側。3V3 は ATOMS3 Lite 表面のピンソケット）:
 *   3V3 -- Rs --+-- ADC
 *               |
 *             R1=10k
 *               |
 *              GND
 */

#include <math.h>
#include <stddef.h>

static constexpr float kDf9Vref = 3.3f;
static constexpr float kDf9R1Ohm = 10000.0f;
static constexpr float kDf9ForceMaxKg = 2.0f;
static constexpr float kDf9RsUnloadedOhm = 1000000.0f;

struct Df9TablePoint {
    float force_kg;
    float rs_ohm;
};

// force_kg, Rs_ohm。抵抗は力増加で単調減少
static constexpr Df9TablePoint kDf9Table[] = {
    {0.20f, 11200.0f},
    {0.40f, 6070.0f},
    {0.60f, 4310.0f},
    {0.80f, 3430.0f},
    {1.00f, 2970.0f},
    {1.20f, 2670.0f},
    {1.40f, 2480.0f},
    {1.60f, 2300.0f},
    {1.80f, 2190.0f},
    {2.00f, 2080.0f},
};

static constexpr size_t kDf9TableLen = sizeof(kDf9Table) / sizeof(kDf9Table[0]);

inline float df9Clamp(float x, float lo, float hi) {
    if (x < lo) {
        return lo;
    }
    if (x > hi) {
        return hi;
    }
    return x;
}

/** 分圧電圧 [V] → センサー抵抗 [Ω] */
inline float df9VoltageToRs(float voltage_v) {
    if (voltage_v < 0.02f) {
        return 10000000.0f;
    }
    const float rs = kDf9R1Ohm * (kDf9Vref / voltage_v - 1.0f);
    return (rs < 1.0f) ? 1.0f : rs;
}

/** センサー抵抗 [Ω] → 力 [kg]（log-log 区間補間） */
inline float df9RsToForceKg(float rs) {
    if (rs >= kDf9RsUnloadedOhm) {
        return 0.0f;
    }

    const Df9TablePoint* table = kDf9Table;
    if (rs >= table[0].rs_ohm) {
        const float r0 = kDf9RsUnloadedOhm;
        const float f1 = table[0].force_kg;
        const float r1 = table[0].rs_ohm;
        if (rs >= r0) {
            return 0.0f;
        }
        const float f0 = 0.005f;
        const float t = (logf(rs) - logf(r0)) / (logf(r1) - logf(r0));
        const float force = f0 * expf(t * (logf(f1) - logf(f0)));
        return df9Clamp(force, 0.0f, kDf9ForceMaxKg);
    }

    if (rs <= table[kDf9TableLen - 1].rs_ohm) {
        return kDf9ForceMaxKg;
    }

    for (size_t i = 0; i + 1 < kDf9TableLen; ++i) {
        const float f1 = table[i].force_kg;
        const float r1 = table[i].rs_ohm;
        const float f2 = table[i + 1].force_kg;
        const float r2 = table[i + 1].rs_ohm;
        if (r1 >= rs && rs >= r2) {
            if (r1 == r2) {
                return f1;
            }
            const float t = (logf(rs) - logf(r1)) / (logf(r2) - logf(r1));
            const float log_f = logf(f1) + t * (logf(f2) - logf(f1));
            return df9Clamp(expf(log_f), 0.0f, kDf9ForceMaxKg);
        }
    }
    return 0.0f;
}

inline float df9VoltageToForceKg(float voltage_v) {
    return df9RsToForceKg(df9VoltageToRs(voltage_v));
}
