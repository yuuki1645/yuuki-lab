#pragma once

#include <stdint.h>

/**
 * 論理関節 → 物理 I2C / サーボ経路の対応。
 *
 * hub == 0 は Grove 直結（MUX なし）。
 * hub_ch は hub != 0 のときだけ意味を持つ（0〜5）。
 *
 * 既定（機体の典型）:
 *   サーボ = Hub 手前の 8Servos 0x25 の ch i（0〜7）
 *   関節 0〜5 の AS5600 = PaHub 0x70 CHi（PaHub は 6 ch）
 *   関節 6〜7 のエンコーダは未割当（enc_addr=0）。別 Hub をプロファイルで足す
 *   INA226 は関節ごとに経路を持つ。既定は 0〜1 のみ PaHub 0x71 CHi。
 *   2 軸目以降はプロファイル／SCAN 仮割当で足す（addr=0 なら未割当・非読取）
 */
#pragma pack(push, 1)
struct JointRoute {
    uint8_t enc_hub;    // 0=root, 例 0x70
    int8_t enc_ch;      // hub 時 0..5、root なら -1
    uint8_t enc_addr;   // 通常 0x36
    uint8_t act_hub;    // 0=root
    int8_t act_ch;      // hub 時 0..5、root なら -1
    uint8_t act_addr;   // 通常 0x25
    uint8_t servo_ch;   // 8Servos の論理 ch
    uint8_t ina_hub;    // 0=root, 例 0x71
    int8_t ina_ch;      // hub 時 0..5、root なら -1
    uint8_t ina_addr;   // 通常 0x41。0 ならこの関節に INA なし
};
#pragma pack(pop)

static constexpr uint8_t kProfEncAddrDefault = 0x36;
static constexpr uint8_t kProfActAddrDefault = 0x25;
static constexpr uint8_t kProfAsHubDefault = 0x70;
static constexpr uint8_t kProfInaHubDefault = 0x71;
static constexpr uint8_t kProfInaAddrDefault = 0x41;
/** 既定プロファイルで INA を付ける軸数（機体の典型は PaHub 0x71 CH0/CH1） */
static constexpr int kProfInaDefaultCount = 2;
