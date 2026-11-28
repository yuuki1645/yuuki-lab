#pragma once

/**
 * 歩行の方策を 1 周期ぶん進める。
 *
 * スイッチは USB 0x92。起動時は切れている。切れているあいだは関節指令を変えない。
 * 入っていてセンサが揃えばネットを回し、欠測なら RDS 135° / SM105BL 0° を指令する。
 * その保持はトルクを切らない。トルクを切るのは従来の Hold コマンド。
 *
 * 最初にネットを回すのは、重力が直立に見える周期から。軸が違えば指令を出さない。
 */

#include <stdint.h>

#include "topology.hpp"

enum PolicyReason : uint8_t {
    kPolicyReasonOff = 0,
    kPolicyReasonRan = 1,
    kPolicyReasonJoint = 2,
    kPolicyReasonImu = 3,
    kPolicyReasonFoot = 4,
    kPolicyReasonNotUpright = 5,
    kPolicyReasonFault = 6,
};

/** 足裏。並びは CAN と同じで [0] が右、[1] が左。mv はミリボルト。 */
struct PolicyFoot {
    uint8_t ok;
    uint8_t mask;
    uint16_t mv[4];
};

struct PolicySense {
    const float* corr_deg;
    const uint8_t* as_ok;
    const uint8_t* map_ok;
    const PolicyFoot* foot;
    /** 過電流か通信途絶。このときは指令を書き換えない。 */
    bool fault;
};

struct PolicyStep {
    /** true なら cmd_deg を全軸へ書く。false なら gCmd に触らない。 */
    bool write_cmd;
    bool ran;
    uint8_t reason;
    float cmd_deg[kCoreJoints];
    float gravity[3];
    float gyro_rad[3];
    float vx_mps;
    uint32_t elapsed_us;
};

struct PolicyView {
    uint8_t enable;
    uint8_t ran;
    uint8_t reason;
    float gravity[3];
    float gyro_rad[3];
    float vx_mps;
};

/** USB タスクから。vx は 0〜0.2 m/s。切るときは vx を 0 にする。 */
void policyRequest(bool enable, float vx_mps);

bool policyRequested();

/** 制御タスクから。enable が切れていれば write_cmd は false。 */
void policyStep(const PolicySense& sense, PolicyStep& out);

/**
 * 状態通知を出す周期なら true。入っているあいだ、おおよそ 5 Hz。
 * USB タスクから呼ぶ。
 */
bool policyTakeStatus(PolicyView& out);
