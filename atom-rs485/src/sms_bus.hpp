/**
 * SM105BL（Feetech SMS、RS485、FT-SCS）の半二重トランザクション。
 *
 * ATOMIC RS485 ベースは DE を ATOM に出さない。UART の送信が終わるまで
 * ドライバがバスを占有し、自分のパケットが受信側にエコーすることがある。
 * エコーは捨てて、その後ろのステータスパケットだけを採用する。
 *
 * 16bit は下位バイトが先。ビット15が方向のレジスタは、書くときにこちらで符号化する。
 * EEPROM（ID、ボーレート、保護）はここでは書かない。試験中にバスを失わないため。
 */

#pragma once

#include <Arduino.h>

// 公式の AtomS3R + Atomic RS485 例。受信が GPIO5、送信が GPIO6。
// 脚の CAN ベースは送信 GPIO5・受信 GPIO6 なので、ピンの向きが逆。
static constexpr int kRs485RxPin = 5;
static constexpr int kRs485TxPin = 6;
static constexpr uint32_t kRs485Baud = 115200;

// 出荷時。GUI の id コマンドでバス上の宛先だけ変える（サーボの EEPROM は変えない）。
static constexpr uint8_t kDefaultServoId = 1;

// 応答がこの時間来なければ、そのトランザクションは失敗。115200 なら往復は数 ms。
static constexpr uint32_t kReplyTimeoutMs = 30;

// SRAM。40 から 31 バイト読むと、制御量とフィードバックが 1 回で揃う。
static constexpr uint8_t kRegTorque = 40;
static constexpr uint8_t kRegAcc = 41;
static constexpr uint8_t kRegGoal = 42;
static constexpr uint8_t kRegSpeed = 46;
static constexpr uint8_t kRegTorqueLimit = 48;
static constexpr uint8_t kRegPresent = 56;
static constexpr uint8_t kRegBlock = 40;
static constexpr uint8_t kRegBlockLen = 31;

// トルクスイッチ。128 は現在位置を 2048 にする校正なので、このファームからは出さない。
static constexpr uint8_t kTorqueOff = 0;
static constexpr uint8_t kTorqueOn = 1;
static constexpr uint8_t kTorqueDamp = 2;

struct SmsReply {
    bool ok;
    uint8_t status;
    uint8_t data[64];
    uint8_t len;
};

void smsBegin();
bool smsSelfOk();
void smsSetId(uint8_t id);
uint8_t smsId();

// 直前にバスへ出したパケット。失敗ログ用。ヌル終端の 16 進。
const char* smsLastTxHex();

bool smsPing(SmsReply* reply);
bool smsRead(uint8_t addr, uint8_t len, SmsReply* reply);
bool smsWrite(uint8_t addr, const uint8_t* data, uint8_t dataLen, SmsReply* reply);
bool smsWrite8(uint8_t addr, uint8_t value, SmsReply* reply);
bool smsWrite16(uint8_t addr, uint16_t valueLe, SmsReply* reply);

// 正はそのまま、負は絶対値のビット15を立てる。大きさは 0〜32767。
uint16_t smsEncodeSigned15(int32_t value);
