#pragma once

/**
 * 機体の配線表。正本はこのファイルだけ。
 *
 * 各脚の ATOM S3R は、起動時に見えた PaHub で右か左かを決め、
 * ここに書いた表を使う。腰は CAN で配線表を送らない。
 * 直すときは、動いた端子の1行だけを書き換えて、両脚へ同じファームを書き込む。
 *
 * 1行が PaHub の1チャンネル。アドレス（角度 0x36、電流 0x41、
 * すねのサーボ 0x25、足裏 0x28）は表に書かない。
 * 股とひざのサーボは PaHub の先ではなく、Grove 直下 0x26 の出力 0、1、2。
 *
 * 軸の番号は股ロール、股ピッチ、ひざ、かかとピッチ、かかとロール。
 */

#include <stdint.h>

#include "joint_profile.hpp"

static constexpr int kCoreJoints = 10;
static constexpr int kCoreFeet = 2;
static constexpr int kAxesPerLeg = 5;
static constexpr int kHubChannels = 6;

static constexpr uint8_t kHubRightThigh = 0x70;
static constexpr uint8_t kHubLeftThigh = 0x71;
static constexpr uint8_t kHubRightShin = 0x72;
static constexpr uint8_t kHubLeftShin = 0x73;

static constexpr uint8_t kAs5600Addr = 0x36;
static constexpr uint8_t kInaAddr = 0x41;
static constexpr uint8_t kServoAddr = 0x25;
static constexpr uint8_t kRootServoAddr = 0x26;
static constexpr uint8_t kFootAddr = 0x28;

static constexpr uint8_t kAxisHipRoll = 0;
static constexpr uint8_t kAxisHipPitch = 1;
static constexpr uint8_t kAxisKnee = 2;
static constexpr uint8_t kAxisAnklePitch = 3;
static constexpr uint8_t kAxisAnkleRoll = 4;

static constexpr uint8_t kSlotEncoder = 1;
static constexpr uint8_t kSlotIna = 2;
static constexpr uint8_t kSlotAnkle = 3;
static constexpr uint8_t kSlotFoot = 4;

/** 股・ひざは直下 0x26。並びは股ロール、股ピッチ、ひざ。 */
static constexpr uint8_t kDirectServoOut[3] = {0, 1, 2};

struct HubSlot {
    uint8_t kind;
    uint8_t axis;
    uint8_t pitchOut;
    uint8_t rollOut;
};

constexpr HubSlot encoder(uint8_t axis) {
    return HubSlot{kSlotEncoder, axis, 0, 0};
}

constexpr HubSlot ina(uint8_t axis) {
    return HubSlot{kSlotIna, axis, 0, 0};
}

constexpr HubSlot ankleBoard(uint8_t pitchOut, uint8_t rollOut) {
    return HubSlot{kSlotAnkle, 0, pitchOut, rollOut};
}

constexpr HubSlot footSlot() {
    return HubSlot{kSlotFoot, 0, 0, 0};
}

// 右もも 0x70
static constexpr HubSlot kRightThigh[kHubChannels] = {
    /* 0 */ ina(kAxisHipRoll),
    /* 1 */ ina(kAxisHipPitch),
    /* 2 */ ina(kAxisKnee),
    /* 3 */ encoder(kAxisKnee),
    /* 4 */ encoder(kAxisHipPitch),
    /* 5 */ encoder(kAxisHipRoll),
};

// 右すね 0x72。かかとのサーボ基板はチャンネル 0、出力 6 がピッチ、7 がロール。
static constexpr HubSlot kRightShin[kHubChannels] = {
    /* 0 */ ankleBoard(6, 7),
    /* 1 */ footSlot(),
    /* 2 */ encoder(kAxisAnklePitch),
    /* 3 */ encoder(kAxisAnkleRoll),
    /* 4 */ ina(kAxisAnkleRoll),
    /* 5 */ ina(kAxisAnklePitch),
};

// 左もも 0x71
static constexpr HubSlot kLeftThigh[kHubChannels] = {
    /* 0 */ encoder(kAxisHipRoll),
    /* 1 */ encoder(kAxisHipPitch),
    /* 2 */ encoder(kAxisKnee),
    /* 3 */ ina(kAxisKnee),
    /* 4 */ ina(kAxisHipPitch),
    /* 5 */ ina(kAxisHipRoll),
};

// 左すね 0x73。かかとのサーボ基板はチャンネル 5。出力番号は右と同じ。
static constexpr HubSlot kLeftShin[kHubChannels] = {
    /* 0 */ ina(kAxisAnklePitch),
    /* 1 */ ina(kAxisAnkleRoll),
    /* 2 */ encoder(kAxisAnkleRoll),
    /* 3 */ encoder(kAxisAnklePitch),
    /* 4 */ footSlot(),
    /* 5 */ ankleBoard(6, 7),
};

constexpr int countSlots(const HubSlot* slots, int n, int i, uint8_t kind, int axisOrNeg) {
    return i >= n ? 0
                  : ((slots[i].kind == kind && (axisOrNeg < 0 || slots[i].axis == axisOrNeg)) ? 1 : 0) +
                        countSlots(slots, n, i + 1, kind, axisOrNeg);
}

constexpr bool ankleOutsOk(const HubSlot* slots, int n, int i) {
    return i >= n ? true
                  : (slots[i].kind != kSlotAnkle
                         ? ankleOutsOk(slots, n, i + 1)
                         : slots[i].pitchOut != slots[i].rollOut && slots[i].pitchOut != 0 &&
                               slots[i].pitchOut != 1 && slots[i].pitchOut != 2 && slots[i].rollOut != 0 &&
                               slots[i].rollOut != 1 && slots[i].rollOut != 2 && ankleOutsOk(slots, n, i + 1));
}

constexpr bool legTableOk(const HubSlot* thigh, const HubSlot* shin) {
    return countSlots(shin, kHubChannels, 0, kSlotAnkle, -1) == 1 &&
           countSlots(thigh, kHubChannels, 0, kSlotAnkle, -1) == 0 &&
           countSlots(shin, kHubChannels, 0, kSlotFoot, -1) == 1 &&
           countSlots(thigh, kHubChannels, 0, kSlotFoot, -1) == 0 && ankleOutsOk(shin, kHubChannels, 0) &&
           countSlots(thigh, kHubChannels, 0, kSlotEncoder, kAxisHipRoll) +
                   countSlots(shin, kHubChannels, 0, kSlotEncoder, kAxisHipRoll) ==
               1 &&
           countSlots(thigh, kHubChannels, 0, kSlotEncoder, kAxisHipPitch) +
                   countSlots(shin, kHubChannels, 0, kSlotEncoder, kAxisHipPitch) ==
               1 &&
           countSlots(thigh, kHubChannels, 0, kSlotEncoder, kAxisKnee) +
                   countSlots(shin, kHubChannels, 0, kSlotEncoder, kAxisKnee) ==
               1 &&
           countSlots(thigh, kHubChannels, 0, kSlotEncoder, kAxisAnklePitch) +
                   countSlots(shin, kHubChannels, 0, kSlotEncoder, kAxisAnklePitch) ==
               1 &&
           countSlots(thigh, kHubChannels, 0, kSlotEncoder, kAxisAnkleRoll) +
                   countSlots(shin, kHubChannels, 0, kSlotEncoder, kAxisAnkleRoll) ==
               1 &&
           countSlots(thigh, kHubChannels, 0, kSlotIna, kAxisHipRoll) +
                   countSlots(shin, kHubChannels, 0, kSlotIna, kAxisHipRoll) ==
               1 &&
           countSlots(thigh, kHubChannels, 0, kSlotIna, kAxisHipPitch) +
                   countSlots(shin, kHubChannels, 0, kSlotIna, kAxisHipPitch) ==
               1 &&
           countSlots(thigh, kHubChannels, 0, kSlotIna, kAxisKnee) +
                   countSlots(shin, kHubChannels, 0, kSlotIna, kAxisKnee) ==
               1 &&
           countSlots(thigh, kHubChannels, 0, kSlotIna, kAxisAnklePitch) +
                   countSlots(shin, kHubChannels, 0, kSlotIna, kAxisAnklePitch) ==
               1 &&
           countSlots(thigh, kHubChannels, 0, kSlotIna, kAxisAnkleRoll) +
                   countSlots(shin, kHubChannels, 0, kSlotIna, kAxisAnkleRoll) ==
               1;
}

static_assert(legTableOk(kRightThigh, kRightShin), "右脚の配線表が欠けているか、端子が重なっています");
static_assert(legTableOk(kLeftThigh, kLeftShin), "左脚の配線表が欠けているか、端子が重なっています");
static_assert(kDirectServoOut[0] != kDirectServoOut[1] && kDirectServoOut[1] != kDirectServoOut[2],
              "直下サーボの出力が重なっています");

inline int channelOf(const HubSlot* slots, uint8_t kind, int axisOrNeg) {
    for (int i = 0; i < kHubChannels; ++i) {
        if (slots[i].kind == kind && (axisOrNeg < 0 || slots[i].axis == static_cast<uint8_t>(axisOrNeg))) {
            return i;
        }
    }
    return -1;
}

/** ももとすねの表から、片脚 5 軸の JointRoute を作る。 */
inline void fillLegRoutes(JointRoute* joint, uint8_t thighHub, const HubSlot* thigh, uint8_t shinHub,
                          const HubSlot* shin) {
    for (int axis = 0; axis < kAxesPerLeg; ++axis) {
        const int encThigh = channelOf(thigh, kSlotEncoder, axis);
        const int encShin = channelOf(shin, kSlotEncoder, axis);
        const bool encOnThigh = encThigh >= 0;
        const int inaThigh = channelOf(thigh, kSlotIna, axis);
        const int inaShin = channelOf(shin, kSlotIna, axis);
        const bool inaOnThigh = inaThigh >= 0;
        uint8_t actHub = 0;
        int8_t actCh = -1;
        uint8_t actAddr = kRootServoAddr;
        uint8_t servoCh = axis < 3 ? kDirectServoOut[axis] : 0;
        if (axis >= kAxisAnklePitch) {
            const int board = channelOf(shin, kSlotAnkle, -1);
            const HubSlot& slot = shin[board];
            actHub = shinHub;
            actCh = static_cast<int8_t>(board);
            actAddr = kServoAddr;
            servoCh = axis == kAxisAnklePitch ? slot.pitchOut : slot.rollOut;
        }
        joint[axis] = JointRoute{
            encOnThigh ? thighHub : shinHub,
            static_cast<int8_t>(encOnThigh ? encThigh : encShin),
            kAs5600Addr,
            actHub,
            actCh,
            actAddr,
            servoCh,
            inaOnThigh ? thighHub : shinHub,
            static_cast<int8_t>(inaOnThigh ? inaThigh : inaShin),
            kInaAddr,
        };
    }
}

inline void fillRightLegRoutes(JointRoute* joint) {
    fillLegRoutes(joint, kHubRightThigh, kRightThigh, kHubRightShin, kRightShin);
}

inline void fillLeftLegRoutes(JointRoute* joint) {
    fillLegRoutes(joint, kHubLeftThigh, kLeftThigh, kHubLeftShin, kLeftShin);
}

inline void fillDefaultTopology(JointRoute* joints, FootRoute* feet) {
    fillRightLegRoutes(joints + 0);
    fillLeftLegRoutes(joints + kAxesPerLeg);
    feet[0] = FootRoute{kHubRightShin, static_cast<int8_t>(channelOf(kRightShin, kSlotFoot, -1)), kFootAddr};
    feet[1] = FootRoute{kHubLeftShin, static_cast<int8_t>(channelOf(kLeftShin, kSlotFoot, -1)), kFootAddr};
}
