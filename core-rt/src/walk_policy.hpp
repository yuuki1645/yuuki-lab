#pragma once

/**
 * 歩行の方策を 1 周期ぶん進める。
 *
 * スイッチは USB 0x92。起動時は切れている。切れているあいだは関節指令を変えない。
 * 入っていてセンサが揃えばネットを回す。欠測や飛びは、今の目標から直立へ
 * サーボの最高速度以内で戻す。トルクは残す。トルクを切るのは従来の Hold コマンド。
 * 目標の変化も同じ最高速度まで。直立指令のまま範囲の外が続くとネットを止め、
 * 計測がさらに外へ逃げるときは目標をその場で固定する。
 *
 * 最初にネットを回すのは、重力が直立に見える周期から。軸が違えば指令を出さない。
 */

#include <stdint.h>

#include "topology.hpp"
#include "usb_frame.hpp"

enum PolicyReason : uint8_t {
    kPolicyReasonOff = 0,
    kPolicyReasonRan = 1,
    kPolicyReasonJoint = 2,
    kPolicyReasonImu = 3,
    kPolicyReasonFoot = 4,
    kPolicyReasonNotUpright = 5,
    kPolicyReasonFault = 6,
    /** 前進 0 のまま、直立の包絡の外が続いた。 */
    kPolicyReasonEnvelope = 7,
    /** 戻しているあいだに、計測がさらに外へ逃げた。目標は動かさない。 */
    kPolicyReasonFrozen = 8,
};

/** 関節の旗。分布の平均に入れるのは有効だけ。 */
static constexpr uint8_t kJointFlagValid = 0;
static constexpr uint8_t kJointFlagMissing = 1;
static constexpr uint8_t kJointFlagJump = 2;
static constexpr uint8_t kJointFlagShake = 3;

/** その周期の安全。0 以外の周期は分布の平均から外す。 */
static constexpr uint8_t kPolicySafetyNone = 0;
static constexpr uint8_t kPolicySafetyRate = 1;
static constexpr uint8_t kPolicySafetyEnvelope = 2;
static constexpr uint8_t kPolicySafetyFreeze = 3;

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
    /** いま出している目標（度）。ファームの軸順。方策が切れている周期の記録に使う。 */
    const float* cmd_deg;
    /** その関節の値が何ミリ秒前か。ファームの軸順。未知は 65535。 */
    const uint16_t* age_joint_ms;
    uint16_t age_imu_ms;
    uint16_t age_foot_ms;
    uint32_t period_us;
    uint32_t sense_us;
    uint8_t overrun;
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
    uint8_t safety;
};

struct PolicyView {
    uint8_t enable;
    uint8_t ran;
    uint8_t reason;
    float gravity[3];
    float gyro_rad[3];
    float vx_mps;
    uint8_t safety;
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

/**
 * 制御周期の記録を 1 通取る。USB タスクから。
 * 次の周期で上書きされる前に送れなければ、その 1 通は捨てる。
 */
bool policyTakeTrace(UsbPolicyTrace& out);
