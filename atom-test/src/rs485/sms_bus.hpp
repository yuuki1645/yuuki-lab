/**
 * SM105BL（Feetech SMS、RS485）の半二重トランザクション。
 *
 * LTC1480 は DE を自分で上げ下げする。/RE は GND に固定するので、受信は常時オン。
 * 自分が送った列が RO に戻る。それはエコーとして 1 回捨て、後ろのステータスだけを使う。
 *
 * 配線（ATOM S3R の底面）:
 *   GPIO6 → DI（4）   GPIO5 ← RO（1）   GPIO7 → DE（3）
 *   /RE（2）→ GND    VCC（8）→ 3.3V    GND（5）→ 共通 GND
 *   A（6）→ サーボのピン 4    B（7）→ サーボのピン 3
 * VCC は 3.3V。5V を入れると LTC1480 が壊れる。
 * サーボのピン 2 だけが 9〜12.6V。GND は電源と共通。
 *
 * 待受の DE は Low。High のままだとサーボが返事をバスに出せない。
 * ボーレートの初期値は 115200。scan は UART を変えるだけで、サーボの EEPROM は書かない。
 * トルクを入れる WRITE は、現在位置を目標にしたあとに限る。校正の 128 は出さない。
 */

#pragma once

#include <Arduino.h>

// 受信 GPIO5、送信 GPIO6。このラボの CAN ベースは送信と受信が逆。
static constexpr int kRs485RxPin = 5;
static constexpr int kRs485TxPin = 6;
// DE と /RE を結ぶと送信中のエコーが消える。試験では /RE を GND にしてエコーを見る。
static constexpr int kDePin = 7;
static constexpr uint32_t kRs485Baud = 115200;

struct SmsReply {
    bool ok;
    // ステータスパケットの状態バイト。0 ならサーボは異常を立てていない。
    uint8_t status;
    uint8_t data[64];
    uint8_t len;
};

void smsBegin();
bool smsSelfOk();
void smsSetId(uint8_t id);
uint8_t smsId();
void smsSetBaud(uint32_t baud);
uint32_t smsBaud();

// 55 AA 55 AA を送り、同じ列が戻るかを見る。サーボの返事は期待しない。
// 結果は @echo の 1 行。true は送信と受信が一致したとき。
bool smsProbeEcho();

bool smsPing(SmsReply* reply);
// 届いたデータが len 未満なら false。短い成功にしないため。
bool smsRead(uint8_t addr, uint8_t len, SmsReply* reply);
// SRAM へ書く。dataLen は 14 まで。EEPROM（ID、ボーレート）には使わない。
bool smsWrite8(uint8_t addr, uint8_t value, SmsReply* reply);
bool smsWrite16(uint8_t addr, uint16_t valueLe, SmsReply* reply);

// 正はそのまま、負は絶対値のビット15を立てる。大きさは 0〜32767。
uint16_t smsEncodeSigned15(int32_t value);
