#pragma once

/**
 * CoreS3 の初期配線。左右で PaHub のチャンネルは違う。
 *
 * 論理軸 0〜4 が右、5〜9 が左。
 * 順は股ロール、股ピッチ、ひざ、かかとピッチ、かかとロール。
 *
 * もも（右 0x70）
 *   0 INA 股ロール  1 INA 股ピッチ  2 INA ひざ
 *   3 AS5600 ひざ  4 AS5600 股ピッチ  5 AS5600 股ロール
 * すね（右 0x72）
 *   0 8Servos 0x25（出力 6 かかとピッチ、7 かかとロール）
 *   1 足スレーブ 0x28
 *   2 AS5600 かかとピッチ  3 AS5600 かかとロール
 *   4 INA かかとロール  5 INA かかとピッチ
 *
 * もも（左 0x71）
 *   0 AS5600 股ロール  1 AS5600 股ピッチ  2 AS5600 ひざ
 *   3 INA ひざ  4 INA 股ピッチ  5 INA 股ロール
 * すね（左 0x73）
 *   0 INA かかとピッチ  1 INA かかとロール
 *   2 AS5600 かかとロール  3 AS5600 かかとピッチ
 *   4 足スレーブ 0x28
 *   5 8Servos 0x25（出力 6 かかとピッチ、7 かかとロール）
 *
 * 股とひざのサーボは、両脚とも Grove 直下の 8Servos 0x26。
 * 出力 0 股ロール、1 股ピッチ、2 ひざ。
 */

#include <stdint.h>

#include "joint_profile.hpp"

static constexpr int kCoreJoints = 10;
static constexpr int kCoreFeet = 2;
static constexpr int kAxesPerLeg = 5;

static constexpr uint8_t kHubRightThigh = 0x70;
static constexpr uint8_t kHubLeftThigh = 0x71;
static constexpr uint8_t kHubRightShin = 0x72;
static constexpr uint8_t kHubLeftShin = 0x73;

// 純正 AS5600 のアドレス。0x40 は INA226 の別アドレスで、この素子ではない。
static constexpr uint8_t kAs5600Addr = 0x36;
static constexpr uint8_t kInaAddr = 0x41;
// すねの PaHub の向こうにある 8Servos。工場出荷アドレスのまま。
static constexpr uint8_t kServoAddr = 0x25;
// Grove 直下の 8Servos。直下とすねを同時に開いてもぶつからないよう 0x26 にしてある。
static constexpr uint8_t kRootServoAddr = 0x26;
static constexpr uint8_t kFootAddr = 0x28;
static constexpr int8_t kRightShinServoCh = 0;
static constexpr int8_t kLeftShinServoCh = 5;
static constexpr int8_t kRightFootCh = 1;
static constexpr int8_t kLeftFootCh = 4;
static constexpr uint8_t kAnklePitchOut = 6;
static constexpr uint8_t kAnkleRollOut = 7;

/** 右脚 5 軸。サーボの股・ひざは Grove 直下、かかとはすね。 */
inline void fillRightLegRoutes(JointRoute* joint) {
    joint[0] = JointRoute{kHubRightThigh, 5, kAs5600Addr, 0, -1, kRootServoAddr, 0,
                          kHubRightThigh, 0, kInaAddr};
    joint[1] = JointRoute{kHubRightThigh, 4, kAs5600Addr, 0, -1, kRootServoAddr, 1,
                          kHubRightThigh, 1, kInaAddr};
    joint[2] = JointRoute{kHubRightThigh, 3, kAs5600Addr, 0, -1, kRootServoAddr, 2,
                          kHubRightThigh, 2, kInaAddr};
    joint[3] = JointRoute{kHubRightShin, 2, kAs5600Addr, kHubRightShin, kRightShinServoCh,
                          kServoAddr, kAnklePitchOut, kHubRightShin, 5, kInaAddr};
    joint[4] = JointRoute{kHubRightShin, 3, kAs5600Addr, kHubRightShin, kRightShinServoCh,
                          kServoAddr, kAnkleRollOut, kHubRightShin, 4, kInaAddr};
}

/** 左脚 5 軸。チャンネル番号は右と違う。 */
inline void fillLeftLegRoutes(JointRoute* joint) {
    joint[0] = JointRoute{kHubLeftThigh, 0, kAs5600Addr, 0, -1, kRootServoAddr, 0,
                          kHubLeftThigh, 5, kInaAddr};
    joint[1] = JointRoute{kHubLeftThigh, 1, kAs5600Addr, 0, -1, kRootServoAddr, 1,
                          kHubLeftThigh, 4, kInaAddr};
    joint[2] = JointRoute{kHubLeftThigh, 2, kAs5600Addr, 0, -1, kRootServoAddr, 2,
                          kHubLeftThigh, 3, kInaAddr};
    joint[3] = JointRoute{kHubLeftShin, 3, kAs5600Addr, kHubLeftShin, kLeftShinServoCh, kServoAddr,
                          kAnklePitchOut, kHubLeftShin, 0, kInaAddr};
    joint[4] = JointRoute{kHubLeftShin, 2, kAs5600Addr, kHubLeftShin, kLeftShinServoCh, kServoAddr,
                          kAnkleRollOut, kHubLeftShin, 1, kInaAddr};
}

inline void fillDefaultTopology(JointRoute* joints, FootRoute* feet) {
    fillRightLegRoutes(joints + 0);
    fillLeftLegRoutes(joints + kAxesPerLeg);
    feet[0] = FootRoute{kHubRightShin, kRightFootCh, kFootAddr};
    feet[1] = FootRoute{kHubLeftShin, kLeftFootCh, kFootAddr};
}
