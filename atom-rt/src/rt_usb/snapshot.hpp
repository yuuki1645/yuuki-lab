#pragma once

#include <stdint.h>

/**
 * リアルタイム制御 1 周期分のスナップショット。
 *
 * Core 1 が書き、Core 0 がコピーして USB に出す。
 * I2C やサーボはこの構造体には含めない（データだけ）。
 *
 * USB には packed の UsbTelemetry（usb_proto.hpp）として出す。
 */
static constexpr int kSnapJoints = 8;
/** 電源監視枠。論理関節 1 つにつき 1 枠（未割当は ina_addr=0 で読まない） */
static constexpr int kSnapIna = kSnapJoints;

/** 作業モード。Lab は机上（PWM 既定オフ）、Robot は機体（出力オン） */
enum class WorkMode : uint8_t {
    Lab = 0,
    Robot = 1,
};

struct Snapshot {
    uint32_t seq;           // 周期番号
    uint32_t t_period_us;   // 前回開始からの間隔
    uint32_t t_loop_us;     // センサ〜関節制御の合計
    uint32_t t_sense_us;    // センサ取得
    uint32_t t_state_us;    // 状態生成
    uint32_t t_policy_us;   // RL / テスト指令
    uint32_t t_act_us;      // 関節制御
    int32_t jitter_us;      // t_period - 目標周期
    uint8_t overrun;        // 実行時間が目標周期を超えたら 1

    float cmd_deg[kSnapJoints];
    float as5600_raw[kSnapJoints];
    float as5600_unwrapped[kSnapJoints];
    float as5600_corr[kSnapJoints];
    uint8_t as5600_ok[kSnapJoints];
    uint8_t map_ok[kSnapJoints];
    uint8_t mag_code[kSnapJoints];  // As5600::statusToCode
    uint8_t agc[kSnapJoints];         // 読めなければ 255

    float ina_volt[kSnapIna];
    float ina_amp[kSnapIna];
    float ina_watt[kSnapIna];
    uint8_t ina_ok[kSnapIna];

    uint16_t i2c_err;       // 累計（センサ欠測の回数）
    uint8_t servo_ok;
    uint8_t mode;            // WorkMode
    uint8_t out_mask;       // bit i が立っていたら軸 i へ PWM

    /** 右足スレーブ。未割当・欠測時は foot_ok=0、mv は 0 */
    uint8_t foot_ok;
    uint8_t foot_mask;      // bit0..3 = TL/TR/BR/BL
    uint32_t foot_seq;
    uint16_t foot_mv[4];    // ミリボルト。並びは TL, TR, BR, BL
};
