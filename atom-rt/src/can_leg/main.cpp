/**
 * 片脚の ATOM S3R。自分の Grove でセンサーを読み、CAN で腰へ渡す。
 * サーボ指令は腰から受け取り、8Servos に書く。
 *
 * pio run -e can-leg -t upload
 * 本線へ戻すときは pio run -e rt-usb -t upload。
 *
 * Atomic CAN ベースは GPIO5 が送信、GPIO6 が受信。
 * Grove は G2=SDA、G1=SCL。この脚の PaHub だけを見る。
 * 役割はアドレスで決める。0x70 / 0x72 が右、0x71 / 0x73 が左。
 * 両方ある、またはどちらも無いときは PWM を出さない。
 *
 * 校正は持たない。配線はファームの既定表で、見えた PaHub が右か左かを決める。
 * CAN の配線表は採用しない。届いてもサーボは初期化し直さない。
 * サーボは 2 枚。Grove 直下 0x26 が股とひざ、すねの 0x25 がかかと。
 * 指令が 200 ms 途切れたら、最後の角度のあとピンを入力にして脱力する。
 */

#include <Arduino.h>
#include <M5_UNIT_8SERVO.h>
#include <math.h>
#include <string.h>

#include "as5600.hpp"
#include "can_leg.hpp"
#include "driver/twai.h"
#include "i2c_foot_proto.h"
#include "ina226.hpp"
#include "pahub.hpp"
#include "topology.hpp"
#include "usb_frame.hpp"

static constexpr int kSdaPin = 2;
static constexpr int kSclPin = 1;
static constexpr int kCanTxPin = 5;
static constexpr int kCanRxPin = 6;
static constexpr uint32_t kI2cHz = 100000;
static constexpr uint32_t kI2cTimeoutMs = 20;
static constexpr uint32_t kHubProbeTimeoutMs = 5;
static constexpr uint32_t kMuxSettleUs = 2000;
static constexpr uint32_t kPeriodMs = 50;
static constexpr float kOvercurrentAmp = 8.0f;

static constexpr float kServoFullMinDeg = 0.0f;
static constexpr float kServoFullMaxDeg = 270.0f;
static constexpr uint16_t kPulseMinUs = 500;
static constexpr uint16_t kPulseMaxUs = 2500;
static constexpr float kMoveMinDeg = 40.0f;
static constexpr float kMoveMaxDeg = 230.0f;

static constexpr uint8_t kHubList[] = {kHubRightThigh, kHubLeftThigh, kHubRightShin, kHubLeftShin};

static As5600 gAs;
static Ina226 gIna[kCanAxes];
static bool gInaReady[kCanAxes] = {};
static bool gServoReady = false;
static bool gCanReady = false;

static uint8_t gRole = kCanRoleUnknown;
static uint8_t gHubMask = 0;
static JointRoute gRoute[kCanAxes];
static FootRoute gFoot{};
static uint8_t gJointEn = 0x1F;
static uint8_t gFootEn = 1;

static CanLegCommand gCmd{};
static uint8_t gAppliedSeq = 0;
static bool gApplied = false;
static uint32_t gCmdMs = 0;
static uint8_t gDriven = 0;
static bool gForceOff = false;
static bool gOver = false;
static uint16_t gI2cErr = 0;
static uint8_t gSeq = 1;

static uint8_t gScanSeq = 0;
static bool gScanReq = false;
static bool gIdentify = false;

static bool canSend(uint32_t id, const uint8_t* data) {
    if (!gCanReady) {
        return false;
    }
    twai_message_t msg{};
    msg.identifier = id;
    msg.data_length_code = 8;
    memcpy(msg.data, data, 8);
    if (twai_transmit(&msg, pdMS_TO_TICKS(20)) != ESP_OK) {
        twai_clear_transmit_queue();
        return false;
    }
    return true;
}

static void canRecover() {
    if (!gCanReady) {
        return;
    }
    twai_status_info_t status{};
    if (twai_get_status_info(&status) != ESP_OK) {
        return;
    }
    if (status.state == TWAI_STATE_BUS_OFF) {
        twai_initiate_recovery();
    } else if (status.state == TWAI_STATE_STOPPED) {
        twai_start();
    }
}

static bool canStart() {
    twai_general_config_t general = TWAI_GENERAL_CONFIG_DEFAULT(
        static_cast<gpio_num_t>(kCanTxPin), static_cast<gpio_num_t>(kCanRxPin), TWAI_MODE_NORMAL);
    general.rx_queue_len = 32;
    general.tx_queue_len = 24;
    const twai_timing_config_t timing = TWAI_TIMING_CONFIG_500KBITS();
    const twai_filter_config_t filter = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    if (twai_driver_install(&general, &timing, &filter) != ESP_OK) {
        return false;
    }
    if (twai_start() != ESP_OK) {
        return false;
    }
    gCanReady = true;
    return true;
}

static int legIndex() {
    return gRole == kCanRoleLeft ? 1 : 0;
}

static bool i2cPing(uint8_t addr) {
    Wire.beginTransmission(addr);
    return Wire.endTransmission() == 0;
}

static void closeHubs() {
    for (uint8_t addr : kHubList) {
        if ((gHubMask & (1u << (addr - 0x70))) == 0) {
            continue;
        }
        PaHub hub(addr);
        hub.select(-1);
    }
}

static bool openMux(uint8_t hub, int8_t ch) {
    closeHubs();
    if (hub == 0) {
        return true;
    }
    if ((gHubMask & (1u << (hub - 0x70))) == 0) {
        return false;
    }
    PaHub h(hub);
    return h.select(ch);
}

static bool i2cWriteRead(uint8_t addr, uint8_t reg, uint8_t* data, size_t len) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    if (Wire.endTransmission(true) != 0) {
        return false;
    }
    delayMicroseconds(200);
    if (Wire.requestFrom(static_cast<int>(addr), static_cast<int>(len)) != static_cast<int>(len)) {
        return false;
    }
    for (size_t i = 0; i < len; ++i) {
        data[i] = static_cast<uint8_t>(Wire.read());
    }
    return true;
}

static uint16_t u16Le(const uint8_t* p) {
    return static_cast<uint16_t>(p[0] | (static_cast<uint16_t>(p[1]) << 8));
}

static uint32_t u32Le(const uint8_t* p) {
    return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
}

/** 見えた PaHub だけで右か左かを決める。混在と不在は不明。 */
static void detectRole() {
    Wire.setTimeOut(kHubProbeTimeoutMs);
    gHubMask = 0;
    for (int i = 0; i < 4; ++i) {
        if (i2cPing(kHubList[i])) {
            gHubMask = static_cast<uint8_t>(gHubMask | (1u << i));
        }
    }
    Wire.setTimeOut(kI2cTimeoutMs);
    const bool right = (gHubMask & ((1u << 0) | (1u << 2))) != 0;
    const bool left = (gHubMask & ((1u << 1) | (1u << 3))) != 0;
    if (right && !left) {
        gRole = kCanRoleRight;
        fillRightLegRoutes(gRoute);
        gFoot = FootRoute{kHubRightShin, static_cast<int8_t>(channelOf(kRightShin, kSlotFoot, -1)), kFootAddr};
    } else if (left && !right) {
        gRole = kCanRoleLeft;
        fillLeftLegRoutes(gRoute);
        gFoot = FootRoute{kHubLeftShin, static_cast<int8_t>(channelOf(kLeftShin, kSlotFoot, -1)), kFootAddr};
    } else {
        gRole = kCanRoleUnknown;
    }
}

static float clampMove(float deg) {
    if (deg < kMoveMinDeg) {
        return kMoveMinDeg;
    }
    if (deg > kMoveMaxDeg) {
        return kMoveMaxDeg;
    }
    return deg;
}

static uint16_t angleToPulse(float deg) {
    deg = clampMove(deg);
    const float t = (deg - kServoFullMinDeg) / (kServoFullMaxDeg - kServoFullMinDeg);
    const float us = kPulseMinUs + t * static_cast<float>(kPulseMaxUs - kPulseMinUs);
    return static_cast<uint16_t>(us + 0.5f);
}

/** 指定アドレスの 8Servos へ書く。ライブラリの内部アドレスは使わない。 */
static bool writeServo(uint8_t addr, uint8_t reg, const uint8_t* data, size_t len) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    for (size_t i = 0; i < len; ++i) {
        Wire.write(data[i]);
    }
    return Wire.endTransmission() == 0;
}

static bool setServoMode(uint8_t addr, uint8_t pin, uint8_t mode) {
    if (pin > 7) {
        return false;
    }
    // モードレジスタはチャンネル番号そのもの（0x00〜0x07）。
    return writeServo(addr, pin, &mode, 1);
}

static bool setServoPulseUs(uint8_t addr, uint8_t pin, uint16_t pulse) {
    if (pin > 7) {
        return false;
    }
    uint8_t data[2] = {static_cast<uint8_t>(pulse & 0xFF), static_cast<uint8_t>(pulse >> 8)};
    return writeServo(addr, static_cast<uint8_t>(0x60 + pin * 2), data, 2);
}

static bool tryInitServo() {
    if (gRole == kCanRoleUnknown) {
        return false;
    }
    bool any = false;
    for (int i = 0; i < kCanAxes; ++i) {
        const JointRoute& route = gRoute[i];
        if (route.act_addr == 0) {
            continue;
        }
        bool seen = false;
        for (int j = 0; j < i; ++j) {
            const JointRoute& prev = gRoute[j];
            if (prev.act_hub == route.act_hub && prev.act_ch == route.act_ch &&
                prev.act_addr == route.act_addr && prev.servo_ch == route.servo_ch) {
                seen = true;
                break;
            }
        }
        if (seen || !openMux(route.act_hub, route.act_ch)) {
            continue;
        }
        delay(2);
        // 起動直後は、経路にある出力だけを入力にして脱力する。
        if (i2cPing(route.act_addr) &&
            setServoMode(route.act_addr, route.servo_ch, DIGITAL_INPUT_MODE)) {
            any = true;
        }
        closeHubs();
    }
    gServoReady = any;
    return gServoReady;
}

/**
 * サーボへ書く前の待ち。
 * 直下の 8Servos は Grove に常時つながっている。
 * PaHub の先はチャンネルを開いた直後、200 µs では 0x25 がまだ ACK しない。
 * エンコーダ読み（kMuxSettleUs）と同じ時間を置く。
 */
static void settleActuator(uint8_t actHub) {
    if (actHub != 0) {
        delayMicroseconds(kMuxSettleUs);
        return;
    }
    delayMicroseconds(200);
}

/** ピンを入力に戻して脱力する。書けたら true。PaHub を開けなければ false で、次周期にやり直す。 */
static bool releaseAxis(int index) {
    if (!gServoReady) {
        return false;
    }
    const JointRoute& route = gRoute[index];
    if (route.act_addr == 0) {
        return true;
    }
    if (!openMux(route.act_hub, route.act_ch)) {
        return false;
    }
    settleActuator(route.act_hub);
    const bool ok = setServoMode(route.act_addr, route.servo_ch, DIGITAL_INPUT_MODE);
    closeHubs();
    return ok;
}

/**
 * 1 軸へパルスを書く。モード切替とパルスの両方が ACK されたときだけ true。
 * 失敗時は呼び出し側が gDriven を立てないので、次の周期はサーボモードからやり直す。
 * 一度成功した軸はモードを毎周期いじらない。切り直すとパルスが途切れる。
 */
static bool driveAxis(int index, float deg) {
    if (!gServoReady) {
        return false;
    }
    const JointRoute& route = gRoute[index];
    if (route.act_addr == 0 || !openMux(route.act_hub, route.act_ch)) {
        return false;
    }
    settleActuator(route.act_hub);
    bool ok = true;
    if ((gDriven & (1u << index)) == 0) {
        ok = setServoMode(route.act_addr, route.servo_ch, SERVO_CTL_MODE);
    }
    if (ok) {
        ok = setServoPulseUs(route.act_addr, route.servo_ch, angleToPulse(deg));
    }
    closeHubs();
    return ok;
}

static void releaseAll() {
    for (int i = 0; i < kCanAxes; ++i) {
        if ((gDriven & (1u << i)) == 0) {
            continue;
        }
        releaseAxis(i);
    }
    gDriven = 0;
}

static void applyCommand(const CanLegCommand& cmd) {
    gCmdMs = millis();
    gApplied = true;
    gAppliedSeq = cmd.seq;
    if (gOver || (cmd.flags & kCanFlagForceOff) != 0 || cmd.mask == 0) {
        gForceOff = true;
        releaseAll();
        return;
    }
    gForceOff = false;
    for (int i = 0; i < kCanAxes; ++i) {
        if ((cmd.mask & (1u << i)) == 0) {
            // 脱力が書けた軸だけ駆動済みを外す。書けなければ次の指令でやり直す。
            if ((gDriven & (1u << i)) != 0 && releaseAxis(i)) {
                gDriven = static_cast<uint8_t>(gDriven & ~(1u << i));
            }
            continue;
        }
        if (driveAxis(i, static_cast<float>(cmd.deci[i]) / 10.0f)) {
            gDriven = static_cast<uint8_t>(gDriven | (1u << i));
        }
    }
}

static void pollCan() {
    canRecover();
    if (gRole == kCanRoleUnknown) {
        return;
    }
    const int leg = legIndex();
    twai_message_t msg{};
    while (twai_receive(&msg, 0) == ESP_OK) {
        if (msg.data_length_code < 8) {
            continue;
        }
        int gotLeg = -1;
        uint8_t slot = 0;
        if (!canParseCmd(msg.identifier, gotLeg, slot) || gotLeg != leg) {
            continue;
        }
        // kCmdRoute は読まない。配線は起動時の既定表のままにする。
        if (slot == kCmdA || slot == kCmdB) {
            if (canCommandPush(gCmd, slot, msg.data) && gCmd.seq != gAppliedSeq) {
                applyCommand(gCmd);
                gCmd.got = 0;
            }
        } else if (slot == kCmdScan) {
            gScanSeq = msg.data[0];
            gScanReq = true;
        } else if (slot == kCmdIdentify) {
            gIdentify = true;
        }
    }
}

static uint16_t centiOf(bool ok, float deg) {
    if (!ok) {
        return kCanCentiInvalid;
    }
    if (deg < 0.0f) {
        deg = 0.0f;
    }
    if (deg > 360.0f) {
        deg = 360.0f;
    }
    return static_cast<uint16_t>(deg * 100.0f + 0.5f);
}

static void readLeg(CanLegSample& out) {
    canSampleBegin(out, gSeq);
    for (int i = 0; i < kCanAxes; ++i) {
        if ((gJointEn & (1u << i)) != 0 && gRoute[i].enc_addr != 0 &&
            openMux(gRoute[i].enc_hub, gRoute[i].enc_ch)) {
            delayMicroseconds(kMuxSettleUs);
            gAs.setAddress(gRoute[i].enc_addr);
            const As5600::MagnetStatus st = gAs.readMagnetStatus();
            out.mag[i] = As5600::statusToCode(st);
            uint8_t agc = 255;
            if (st != As5600::MagnetStatus::CommError) {
                gAs.readAgc(agc);
            }
            out.agc[i] = agc;
            float deg = 0.0f;
            if (st == As5600::MagnetStatus::Ok && gAs.readDegrees(deg)) {
                out.as_ok = static_cast<uint8_t>(out.as_ok | (1u << i));
                out.centi[i] = centiOf(true, deg);
            } else {
                ++gI2cErr;
            }
            closeHubs();
        }
        if ((gJointEn & (1u << i)) != 0 && gRoute[i].ina_addr != 0 &&
            openMux(gRoute[i].ina_hub, gRoute[i].ina_ch)) {
            delayMicroseconds(200);
            gIna[i].setAddress(gRoute[i].ina_addr);
            if (!gInaReady[i]) {
                gInaReady[i] = gIna[i].isConnected() && gIna[i].begin();
            }
            float volt = 0.0f;
            float amp = 0.0f;
            float watt = 0.0f;
            if (gInaReady[i] && gIna[i].read(volt, amp, watt)) {
                out.ina_ok = static_cast<uint8_t>(out.ina_ok | (1u << i));
                const int mv = static_cast<int>(volt * 1000.0f);
                const int ma = static_cast<int>(amp * 1000.0f);
                out.bus_mv[i] = static_cast<int16_t>(mv > 32000 ? 32000 : (mv < -32000 ? -32000 : mv));
                out.ma[i] = static_cast<int16_t>(ma > 32000 ? 32000 : (ma < -32000 ? -32000 : ma));
                if (fabsf(amp) > kOvercurrentAmp) {
                    gOver = true;
                    releaseAll();
                }
            } else {
                gInaReady[i] = false;
                ++gI2cErr;
            }
            closeHubs();
        }
    }
    if (gFootEn != 0 && gFoot.addr != 0 && openMux(gFoot.hub, gFoot.ch)) {
        delayMicroseconds(300);
        uint8_t hdr[8] = {};
        uint8_t raw[8] = {};
        if (i2cWriteRead(gFoot.addr, kFootRegWhoAmI, hdr, sizeof(hdr)) && hdr[0] == kFootWhoAmIValue &&
            i2cWriteRead(gFoot.addr, kFootRegMv0, raw, sizeof(raw))) {
            out.foot_ok = 1;
            out.foot_mask = hdr[3];
            out.foot_seq = u32Le(&hdr[4]);
            for (int c = 0; c < 4; ++c) {
                out.foot_mv[c] = u16Le(&raw[c * 2]);
            }
        } else {
            ++gI2cErr;
        }
        closeHubs();
    }
}

static void publish(const CanLegSample& sample, uint8_t senseMs) {
    const int leg = gRole == kCanRoleUnknown ? -1 : legIndex();
    const uint32_t helloId = leg < 0 ? kCanUnknownHello : canTelId(leg, kTelHello);
    CanLegHello hello{};
    hello.seq = sample.seq;
    hello.role = gRole;
    hello.hubs = gHubMask;
    hello.servo_ok = gServoReady ? 1 : 0;
    hello.flags = gOver ? kCanFlagOvercurrent : 0;
    hello.i2c_err = gI2cErr;
    hello.sense_ms = senseMs;
    uint8_t raw[8];
    canPackHello(raw, hello);
    canSend(helloId, raw);
    if (leg < 0) {
        return;
    }
    uint8_t frame[10][8];
    canPackSample(frame, sample);
    const uint8_t slots[10] = {kTelAngA, kTelAngB, kTelMag,  kTelAgc,  kTelVoltA,
                               kTelVoltB, kTelAmpA, kTelAmpB, kTelFootA, kTelFootB};
    for (int i = 0; i < 10; ++i) {
        canSend(canTelId(leg, slots[i]), frame[i]);
    }
}

static void runScan() {
    if (gRole == kCanRoleUnknown) {
        return;
    }
    UsbScanNode nodes[24];
    int count = 0;
    const int leg = legIndex();
    // 直下の 0x26 はチャンネルを開くと毎 CH に見える。閉じたまま 1 回だけ載せる。
    closeHubs();
    if (count < 24 && i2cPing(kRootServoAddr)) {
        nodes[count].hub = 0;
        nodes[count].ch = -1;
        nodes[count].addr = kRootServoAddr;
        nodes[count].kind = 4;
        nodes[count].mag = 255;
        nodes[count].agc = 255;
        ++count;
    }
    for (int h = 0; h < 4; ++h) {
        if ((gHubMask & (1u << h)) == 0) {
            continue;
        }
        const uint8_t hub = kHubList[h];
        if (count < 24) {
            nodes[count].hub = 0;
            nodes[count].ch = -1;
            nodes[count].addr = hub;
            nodes[count].kind = 1;
            nodes[count].mag = 255;
            nodes[count].agc = 255;
            ++count;
        }
        for (int ch = 0; ch < PaHub::kChannelCount; ++ch) {
            if (!openMux(hub, static_cast<int8_t>(ch))) {
                continue;
            }
            delayMicroseconds(kMuxSettleUs);
            const uint8_t addrs[] = {kAs5600Addr, kInaAddr, kServoAddr, kFootAddr};
            const uint8_t kinds[] = {2, 3, 4, 5};
            for (int k = 0; k < 4; ++k) {
                if (!i2cPing(addrs[k]) || count >= 24) {
                    continue;
                }
                nodes[count].hub = hub;
                nodes[count].ch = static_cast<int8_t>(ch);
                nodes[count].addr = addrs[k];
                nodes[count].kind = kinds[k];
                nodes[count].mag = 255;
                nodes[count].agc = 255;
                if (kinds[k] == 2) {
                    gAs.setAddress(addrs[k]);
                    nodes[count].mag = As5600::statusToCode(gAs.readMagnetStatus());
                    uint8_t agc = 255;
                    if (gAs.readAgc(agc)) {
                        nodes[count].agc = agc;
                    }
                }
                ++count;
            }
        }
    }
    closeHubs();
    uint8_t head[8] = {};
    head[0] = gScanSeq;
    head[1] = static_cast<uint8_t>(count);
    canSend(canTelId(leg, kTelScanHead), head);
    for (int i = 0; i < count; ++i) {
        uint8_t d[8] = {};
        d[0] = gScanSeq;
        d[1] = static_cast<uint8_t>(i);
        d[2] = nodes[i].hub;
        d[3] = static_cast<uint8_t>(nodes[i].ch);
        d[4] = nodes[i].addr;
        d[5] = nodes[i].kind;
        d[6] = nodes[i].mag;
        d[7] = nodes[i].agc;
        canSend(canTelId(leg, kTelScanNode), d);
    }
}

static void pulseFoot() {
    if (gFoot.addr == 0 || !openMux(gFoot.hub, gFoot.ch)) {
        return;
    }
    delayMicroseconds(200);
    Wire.beginTransmission(gFoot.addr);
    Wire.write(kFootRegLedR);
    Wire.write(40);
    Wire.write(40);
    Wire.write(40);
    Wire.endTransmission();
    closeHubs();
}

static void watchCommand() {
    if (!gApplied || gForceOff || gOver) {
        return;
    }
    if (static_cast<uint32_t>(millis() - gCmdMs) <= kCanStaleMs) {
        return;
    }
    gForceOff = true;
    releaseAll();
}

void setup() {
    Serial.begin(115200);
    Serial.setTxBufferSize(1024);
    delay(200);
    Wire.begin(kSdaPin, kSclPin, kI2cHz);
    Wire.setTimeOut(kI2cTimeoutMs);
    gAs.begin(kSdaPin, kSclPin, kI2cHz);
    detectRole();
    const char* name = gRole == kCanRoleRight ? "right" : gRole == kCanRoleLeft ? "left" : "unknown";
    Serial.printf("can-leg %s hubs=0x%02X\n", name, gHubMask);
    Serial.println(canStart() ? "twai started" : "twai start failed");
    if (gRole != kCanRoleUnknown) {
        tryInitServo();
    }
    closeHubs();
}

void loop() {
    pollCan();
    watchCommand();
    if (gIdentify) {
        gIdentify = false;
        pulseFoot();
    }
    if (gScanReq) {
        gScanReq = false;
        runScan();
    }
    const uint32_t t0 = millis();
    CanLegSample sample{};
    if (gRole == kCanRoleUnknown) {
        canSampleBegin(sample, gSeq);
    } else {
        readLeg(sample);
    }
    sample.seq = gSeq;
    uint32_t sense = millis() - t0;
    if (sense > 255) {
        sense = 255;
    }
    publish(sample, static_cast<uint8_t>(sense));
    gSeq = static_cast<uint8_t>(gSeq + 1);
    if (gSeq == 0) {
        gSeq = 1;
    }
    const uint32_t spent = millis() - t0;
    if (spent < kPeriodMs) {
        delay(kPeriodMs - spent);
    }
}
