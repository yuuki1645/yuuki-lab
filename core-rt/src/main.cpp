/**
 * 腰の CoreS3。両脚 10 軸を 1 本の Grove I2C で 20 Hz 読む。
 *
 * Core 1 が I2C とサーボ。Core 0 が USB。バスは同時に触らない。
 * 内部 I2C（G12/G11、IMU や AW9523）はここでは開かない。
 * 外部は PORT.A の G2=SDA、G1=SCL。
 *
 * 作業モード:
 *   Lab（起動時）  PWM は、出した軸だけ。
 *   Robot         10 軸を 135° で保持。
 *
 * 校正マップは論理軸 0〜9 に結び、64 KB の NVS に残す。
 * USB は ver 15。番号の正本は link/include/usb_frame.hpp。
 */

#include <Arduino.h>
#include <M5_UNIT_8SERVO.h>
#include <Preferences.h>
#include <math.h>
#include <string.h>

#include "as5600.hpp"
#include "i2c_foot_proto.h"
#include "ina226.hpp"
#include "pahub.hpp"
#include "topology.hpp"
#include "usb_proto.hpp"

static constexpr int kSdaPin = 2;
static constexpr int kSclPin = 1;
static constexpr uint32_t kI2cHz = 100000;
static constexpr uint32_t kPeriodUs = 50000;

static constexpr float kServoFullMinDeg = 0.0f;
static constexpr float kServoFullMaxDeg = 270.0f;
static constexpr uint16_t kPulseMinUs = 500;
static constexpr uint16_t kPulseMaxUs = 2500;
static constexpr float kMoveMinDeg = 40.0f;
static constexpr float kMoveMaxDeg = 230.0f;
static constexpr float kHoldDeg = 135.0f;
static constexpr float kOvercurrentAmp = 8.0f;

static constexpr int kRtCore = 1;
static constexpr int kUsbCore = 0;
static constexpr uint32_t kRtStack = 12288;
static constexpr uint32_t kUsbStack = 12288;

enum class WorkMode : uint8_t { Lab = 0, Robot = 1 };

struct CalMap {
    bool ok;
    int count;
    float x[kMapLen];
    float y[kMapLen];
};

struct FootReading {
    uint8_t ok;
    uint8_t mask;
    uint32_t seq;
    uint16_t mv[4];
};

struct Snapshot {
    uint32_t seq;
    uint32_t t_period_us;
    uint32_t t_loop_us;
    uint32_t t_sense_us;
    uint32_t t_state_us;
    uint32_t t_policy_us;
    uint32_t t_act_us;
    int32_t jitter_us;
    uint8_t overrun;
    float cmd_deg[kCoreJoints];
    float raw_deg[kCoreJoints];
    float unwrap_deg[kCoreJoints];
    float corr_deg[kCoreJoints];
    uint8_t as_ok[kCoreJoints];
    uint8_t map_ok[kCoreJoints];
    uint8_t mag[kCoreJoints];
    uint8_t agc[kCoreJoints];
    float volt[kCoreJoints];
    float amp[kCoreJoints];
    float watt[kCoreJoints];
    uint8_t ina_ok[kCoreJoints];
    uint16_t i2c_err;
    uint8_t servo_ok;
    uint8_t mode;
    uint16_t out_mask;
    FootReading foot[kCoreFeet];
};

static As5600 gAs5600;
static Ina226 gIna[kCoreJoints];
static bool gInaReady[kCoreJoints] = {};
static M5_UNIT_8SERVO gServo;
static bool gServoReady = false;

static JointRoute gRoute[kCoreJoints];
static FootRoute gFoot[kCoreFeet];
static uint16_t gJointEn = 0x03FF;  // 10 軸
static uint8_t gFootEn = 0x03;      // bit0 右、bit1 左
static CalMap gCal[kCoreJoints];

static float gUnwrapPrev[kCoreJoints];
static float gUnwrapped[kCoreJoints];
static bool gUnwrapInit[kCoreJoints];
static float gCmd[kCoreJoints];

static WorkMode gMode = WorkMode::Lab;
static uint16_t gOutMask = 0;
static uint16_t gI2cErr = 0;
static float gOverAmp = 0.0f;
static volatile uint8_t gEvtOver = 0;

static Snapshot gSnap;
static portMUX_TYPE gLock = portMUX_INITIALIZER_UNLOCKED;
static portMUX_TYPE gMapLock = portMUX_INITIALIZER_UNLOCKED;
static Preferences gPrefs;

static volatile uint8_t gScanReq = 0;
static volatile uint8_t gIdentifyReq = 0;
static UsbScanNode gScan[48];
static int gScanCount = 0;
static volatile uint8_t gScanReady = 0;

struct MapRx {
    int joint;
    int total;
    int got;
    float x[kMapLen];
    float y[kMapLen];
};
static MapRx gMapRx;
static volatile uint8_t gMapSaveReq = 0;
static int gMapSaveJoint = -1;

// ---------------------------------------------------------------------------
// バス。開いてよい PaHub のポートは、木全体で 1 つだけ。
// ---------------------------------------------------------------------------
static bool i2cPing(uint8_t addr) {
    Wire.beginTransmission(addr);
    return Wire.endTransmission() == 0;
}

static void closeAllHubs() {
    for (uint8_t addr = 0x70; addr <= 0x73; ++addr) {
        PaHub hub(addr);
        hub.select(-1);
    }
}

/** hub==0 は直結（全部閉じるだけ）。それ以外は目的の 1 ポートを開く。 */
static void openMux(uint8_t hub, int8_t ch) {
    closeAllHubs();
    if (hub < 0x70 || hub > 0x77) {
        return;
    }
    PaHub h(hub);
    h.select(ch);
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

// ---------------------------------------------------------------------------
// 角度と校正
// ---------------------------------------------------------------------------
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

static float shortestDelta(float fromDeg, float toDeg) {
    float d = toDeg - fromDeg;
    if (d > 180.0f) {
        d -= 360.0f;
    }
    if (d < -180.0f) {
        d += 360.0f;
    }
    return d;
}

static float unwrapJoint(int i, float raw) {
    if (!gUnwrapInit[i]) {
        gUnwrapPrev[i] = raw;
        gUnwrapped[i] = raw;
        gUnwrapInit[i] = true;
        return raw;
    }
    gUnwrapped[i] += shortestDelta(gUnwrapPrev[i], raw);
    gUnwrapPrev[i] = raw;
    return gUnwrapped[i];
}

static float alignToMap(float u, float x0, float x1) {
    float best = u;
    float bestDist = 1e9f;
    for (int k = -1; k <= 1; ++k) {
        const float cand = u + 360.0f * static_cast<float>(k);
        float d = 0.0f;
        if (cand < x0) {
            d = x0 - cand;
        } else if (cand > x1) {
            d = cand - x1;
        }
        if (d < bestDist) {
            bestDist = d;
            best = cand;
        }
    }
    return best;
}

static float interpMap(const CalMap& map, float u) {
    const int n = map.count;
    if (!map.ok || n < 2) {
        return u;
    }
    u = alignToMap(u, map.x[0], map.x[n - 1]);
    if (u <= map.x[0]) {
        return map.y[0];
    }
    if (u >= map.x[n - 1]) {
        return map.y[n - 1];
    }
    for (int i = 0; i < n - 1; ++i) {
        const float x0 = map.x[i];
        const float x1 = map.x[i + 1];
        if (u >= x0 && u <= x1) {
            const float den = x1 - x0;
            if (fabsf(den) < 1e-4f) {
                return map.y[i];
            }
            return map.y[i] + (u - x0) / den * (map.y[i + 1] - map.y[i]);
        }
    }
    return u;
}

static void calKey(char* buf, size_t n, const char* prefix, int joint) {
    snprintf(buf, n, "%s%d", prefix, joint);
}

static bool prefsOpen(const char* ns, bool readOnly) {
    gPrefs.end();
    return gPrefs.begin(ns, readOnly);
}

static void loadCal() {
    if (!prefsOpen("cal", true)) {
        return;
    }
    for (int i = 0; i < kCoreJoints; ++i) {
        char key[8];
        calKey(key, sizeof(key), "mn", i);
        const int count = gPrefs.getInt(key, 0);
        calKey(key, sizeof(key), "mk", i);
        const bool ok = gPrefs.getBool(key, false) && count >= 2 && count <= kMapLen;
        CalMap tmp{};
        if (ok) {
            const size_t bytes = static_cast<size_t>(count) * sizeof(float);
            calKey(key, sizeof(key), "mx", i);
            const bool xOk = gPrefs.getBytes(key, tmp.x, bytes) == bytes;
            calKey(key, sizeof(key), "my", i);
            const bool yOk = gPrefs.getBytes(key, tmp.y, bytes) == bytes;
            if (xOk && yOk) {
                tmp.ok = true;
                tmp.count = count;
            }
        }
        gCal[i] = tmp;
    }
    gPrefs.end();
}

static bool saveCal(int joint) {
    if (joint < 0 || joint >= kCoreJoints) {
        return false;
    }
    CalMap tmp;
    portENTER_CRITICAL(&gMapLock);
    tmp = gCal[joint];
    portEXIT_CRITICAL(&gMapLock);
    if (!prefsOpen("cal", false)) {
        return false;
    }
    char key[8];
    calKey(key, sizeof(key), "mk", joint);
    gPrefs.putBool(key, tmp.ok);
    calKey(key, sizeof(key), "mn", joint);
    gPrefs.putInt(key, tmp.count);
    bool wrote = true;
    if (tmp.count > 0) {
        const size_t bytes = static_cast<size_t>(tmp.count) * sizeof(float);
        calKey(key, sizeof(key), "mx", joint);
        if (gPrefs.putBytes(key, tmp.x, bytes) != bytes) {
            wrote = false;
        }
        calKey(key, sizeof(key), "my", joint);
        if (gPrefs.putBytes(key, tmp.y, bytes) != bytes) {
            wrote = false;
        }
    }
    gPrefs.end();
    return wrote;
}

static void loadProfile() {
    fillDefaultTopology(gRoute, gFoot);
    if (!prefsOpen("jprof", true)) {
        return;
    }
    JointRoute routes[kCoreJoints];
    FootRoute feet[kCoreFeet];
    const size_t routeBytes = sizeof(routes);
    const size_t footBytes = sizeof(feet);
    const bool routesOk = gPrefs.getBytes("r", routes, routeBytes) == routeBytes;
    const bool feetOk = gPrefs.getBytes("feet", feet, footBytes) == footBytes;
    uint8_t en[3] = {};
    const bool enOk = gPrefs.getBytes("en", en, sizeof(en)) == sizeof(en);
    gPrefs.end();
    if (routesOk && feetOk) {
        memcpy(gRoute, routes, routeBytes);
        memcpy(gFoot, feet, footBytes);
    }
    if (enOk) {
        gJointEn = static_cast<uint16_t>(en[0] | (static_cast<uint16_t>(en[1]) << 8));
        gFootEn = en[2];
    }
}

static bool saveProfile() {
    if (!prefsOpen("jprof", false)) {
        return false;
    }
    const bool routesOk = gPrefs.putBytes("r", gRoute, sizeof(gRoute)) == sizeof(gRoute);
    const bool feetOk = gPrefs.putBytes("feet", gFoot, sizeof(gFoot)) == sizeof(gFoot);
    uint8_t en[3] = {
        static_cast<uint8_t>(gJointEn & 0xFF),
        static_cast<uint8_t>(gJointEn >> 8),
        gFootEn,
    };
    const bool enOk = gPrefs.putBytes("en", en, sizeof(en)) == sizeof(en);
    gPrefs.end();
    return routesOk && feetOk && enOk;
}

// ---------------------------------------------------------------------------
// センサーとサーボ
// ---------------------------------------------------------------------------
static void readFoot(const FootRoute& route, FootReading& out) {
    memset(&out, 0, sizeof(out));
    if (route.addr == 0) {
        return;
    }
    openMux(route.hub, route.ch);
    delayMicroseconds(300);
    uint8_t hdr[8] = {};
    uint8_t raw[8] = {};
    if (i2cWriteRead(route.addr, kFootRegWhoAmI, hdr, sizeof(hdr)) &&
        hdr[0] == kFootWhoAmIValue &&
        i2cWriteRead(route.addr, kFootRegMv0, raw, sizeof(raw))) {
        out.ok = 1;
        out.mask = hdr[3];
        out.seq = u32Le(&hdr[4]);
        for (int c = 0; c < 4; ++c) {
            out.mv[c] = u16Le(&raw[c * 2]);
        }
    } else {
        ++gI2cErr;
    }
    closeAllHubs();
}

static void readSensors(Snapshot& out) {
    // USB タスクが経路を書き換えても、この周期の途中で切れないようにコピーする。
    JointRoute routes[kCoreJoints];
    FootRoute feet[kCoreFeet];
    uint16_t jointEn = 0;
    uint8_t footEn = 0;
    portENTER_CRITICAL(&gLock);
    memcpy(routes, gRoute, sizeof(routes));
    memcpy(feet, gFoot, sizeof(feet));
    jointEn = gJointEn;
    footEn = gFootEn;
    portEXIT_CRITICAL(&gLock);

    for (int i = 0; i < kCoreJoints; ++i) {
        out.mag[i] = 255;
        out.agc[i] = 255;
        out.as_ok[i] = 0;
        out.raw_deg[i] = NAN;
        out.unwrap_deg[i] = NAN;
        out.ina_ok[i] = 0;
        out.volt[i] = NAN;
        out.amp[i] = NAN;
        out.watt[i] = NAN;
        const JointRoute route = routes[i];
        if ((jointEn & (1u << i)) != 0 && route.enc_addr != 0) {
            openMux(route.enc_hub, route.enc_ch);
            delayMicroseconds(300);
            const As5600::MagnetStatus st = gAs5600.readMagnetStatus();
            out.mag[i] = As5600::statusToCode(st);
            uint8_t agc = 255;
            if (st != As5600::MagnetStatus::CommError) {
                gAs5600.readAgc(agc);
            }
            out.agc[i] = agc;
            float raw = 0.0f;
            if (st == As5600::MagnetStatus::Ok && gAs5600.readDegrees(raw)) {
                out.as_ok[i] = 1;
                out.raw_deg[i] = raw;
                out.unwrap_deg[i] = unwrapJoint(i, raw);
            } else {
                ++gI2cErr;
            }
            closeAllHubs();
        }
        if ((jointEn & (1u << i)) != 0 && route.ina_addr != 0) {
            openMux(route.ina_hub, route.ina_ch);
            delayMicroseconds(200);
            gIna[i].setAddress(route.ina_addr);
            if (!gInaReady[i]) {
                gInaReady[i] = gIna[i].isConnected() && gIna[i].begin();
            }
            if (gInaReady[i] && gIna[i].read(out.volt[i], out.amp[i], out.watt[i])) {
                out.ina_ok[i] = 1;
                if (fabsf(out.amp[i]) > kOvercurrentAmp) {
                    gOutMask = 0;
                    gOverAmp = out.amp[i];
                    gEvtOver = 1;
                }
            } else {
                gInaReady[i] = false;
                ++gI2cErr;
            }
            closeAllHubs();
        }
    }
    for (int f = 0; f < kCoreFeet; ++f) {
        if ((footEn & (1u << f)) == 0) {
            memset(&out.foot[f], 0, sizeof(out.foot[f]));
            continue;
        }
        readFoot(feet[f], out.foot[f]);
    }
}

static void writeServos() {
    if (!gServoReady) {
        return;
    }
    JointRoute routes[kCoreJoints];
    uint16_t mask = 0;
    float cmd[kCoreJoints];
    portENTER_CRITICAL(&gLock);
    memcpy(routes, gRoute, sizeof(routes));
    mask = gOutMask;
    memcpy(cmd, gCmd, sizeof(cmd));
    portEXIT_CRITICAL(&gLock);
    for (int i = 0; i < kCoreJoints; ++i) {
        if ((mask & (1u << i)) == 0) {
            continue;
        }
        const JointRoute route = routes[i];
        if (route.act_addr == 0) {
            continue;
        }
        openMux(route.act_hub, route.act_ch);
        delayMicroseconds(200);
        gServo.setServoPulse(route.servo_ch, angleToPulse(cmd[i]));
        closeAllHubs();
    }
}

static bool initServos() {
    // 左右ともアドレスは 0x25。begin は 1 回で、ピンモードはユニットごとに出す。
    const uint8_t hubs[2] = {kHubRightShin, kHubLeftShin};
    bool any = false;
    for (uint8_t hub : hubs) {
        openMux(hub, kServoHubChannel);
        delay(2);
        // 右すねが無い机上でも、応答した側の 8Servos だけ初期化する。
        if (!i2cPing(kServoAddr)) {
            closeAllHubs();
            continue;
        }
        if (!gServoReady) {
            gServoReady = gServo.begin(&Wire, kSdaPin, kSclPin, kServoAddr);
            Wire.setClock(kI2cHz);
        }
        if (gServoReady) {
            for (int ch = 0; ch < kAxesPerLeg; ++ch) {
                gServo.setOnePinMode(static_cast<uint8_t>(ch), SERVO_CTL_MODE);
            }
            any = true;
        }
        closeAllHubs();
    }
    return any;
}

static void runScan() {
    gScanCount = 0;
    const uint8_t hubs[4] = {kHubRightThigh, kHubLeftThigh, kHubRightShin, kHubLeftShin};
    for (uint8_t hub : hubs) {
        closeAllHubs();
        if (!i2cPing(hub)) {
            continue;
        }
        if (gScanCount < 48) {
            UsbScanNode node{};
            node.hub = hub;
            node.ch = -1;
            node.addr = hub;
            node.kind = 1;  // pahub
            node.mag = 255;
            node.agc = 255;
            gScan[gScanCount++] = node;
        }
        for (int ch = 0; ch < PaHub::kChannelCount; ++ch) {
            openMux(hub, static_cast<int8_t>(ch));
            delayMicroseconds(300);
            const uint8_t addrs[] = {kAs5600Addr, kInaAddr, kServoAddr, kFootAddr};
            const uint8_t kinds[] = {2, 3, 4, 5};
            for (int k = 0; k < 4; ++k) {
                if (!i2cPing(addrs[k])) {
                    continue;
                }
                delayMicroseconds(150);
                if (!i2cPing(addrs[k])) {
                    continue;
                }
                if (gScanCount >= 48) {
                    break;
                }
                UsbScanNode node{};
                node.hub = hub;
                node.ch = static_cast<int8_t>(ch);
                node.addr = addrs[k];
                node.kind = kinds[k];
                node.mag = 255;
                node.agc = 255;
                if (kinds[k] == 2) {
                    node.mag = As5600::statusToCode(gAs5600.readMagnetStatus());
                    uint8_t agc = 255;
                    if (gAs5600.readAgc(agc)) {
                        node.agc = agc;
                    }
                }
                gScan[gScanCount++] = node;
            }
        }
    }
    closeAllHubs();
    gScanReady = 1;
}

// ---------------------------------------------------------------------------
// USB
// ---------------------------------------------------------------------------
static void usbHoldRebootOff() {
#if defined(RTC_CNTL_USB_CONF_REG) && defined(RTC_CNTL_USB_RESET_DISABLE)
    REG_SET_BIT(RTC_CNTL_USB_CONF_REG, RTC_CNTL_USB_RESET_DISABLE);
#endif
}

static bool usbSend(uint8_t type, const void* payload, uint16_t len) {
    uint8_t buf[kUsbFrameOverhead + kUsbMaxPayload];
    const size_t n = usbBuildFrame(buf, sizeof(buf), type, payload, len);
    if (n == 0) {
        return false;
    }
    const uint32_t t0 = millis();
    while (Serial.availableForWrite() < static_cast<int>(n)) {
        if ((millis() - t0) > 40) {
            return false;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    return Serial.write(buf, n) == n;
}

static void sendHello() {
    UsbHello15 h{};
    h.ver = kUsbFwVer;
    h.mode = static_cast<uint8_t>(gMode);
    h.joints = kCoreJoints;
    h.ina = kCoreJoints;
    h.servo = gServoReady ? 1 : 0;
    h.board = kUsbBoardCoreS3;
    h.feet = kCoreFeet;
    h.out_mask = gOutMask;
    usbSend(kUsbHello, &h, sizeof(h));
}

static void sendMode() {
    uint8_t raw[3] = {
        static_cast<uint8_t>(gMode),
        static_cast<uint8_t>(gOutMask & 0xFF),
        static_cast<uint8_t>(gOutMask >> 8),
    };
    usbSend(kUsbMode, raw, sizeof(raw));
}

static void sendTelemetry() {
    Snapshot s;
    portENTER_CRITICAL(&gLock);
    s = gSnap;
    portEXIT_CRITICAL(&gLock);
    UsbTelemetry15 t{};
    t.seq = s.seq;
    t.t_period_us = s.t_period_us;
    t.t_loop_us = s.t_loop_us;
    t.t_sense_us = s.t_sense_us;
    t.t_state_us = s.t_state_us;
    t.t_policy_us = s.t_policy_us;
    t.t_act_us = s.t_act_us;
    t.jitter_us = s.jitter_us;
    t.overrun = s.overrun;
    t.i2c_err = s.i2c_err;
    t.servo_ok = s.servo_ok;
    t.mode = s.mode;
    t.out_mask = s.out_mask;
    for (int i = 0; i < kCoreJoints; ++i) {
        t.cmd_deg[i] = s.cmd_deg[i];
        t.raw_deg[i] = s.raw_deg[i];
        t.unwrap_deg[i] = s.unwrap_deg[i];
        t.corr_deg[i] = s.corr_deg[i];
        t.as_ok[i] = s.as_ok[i];
        t.map_ok[i] = s.map_ok[i];
        t.mag[i] = s.mag[i];
        t.agc[i] = s.agc[i];
        t.volt[i] = s.volt[i];
        t.amp[i] = s.amp[i];
        t.watt[i] = s.watt[i];
        t.ina_ok[i] = s.ina_ok[i];
    }
    for (int f = 0; f < kCoreFeet; ++f) {
        t.foot[f].ok = s.foot[f].ok;
        t.foot[f].mask = s.foot[f].mask;
        t.foot[f].seq = s.foot[f].seq;
        memcpy(t.foot[f].mv, s.foot[f].mv, sizeof(t.foot[f].mv));
    }
    usbSend(kUsbTelemetry, &t, sizeof(t));
}

static void sendProfile() {
    uint8_t raw[1 + sizeof(JointRoute) * kCoreJoints + sizeof(FootRoute) * kCoreFeet + 3];
    size_t n = 0;
    raw[n++] = static_cast<uint8_t>(kCoreJoints);
    portENTER_CRITICAL(&gLock);
    memcpy(raw + n, gRoute, sizeof(gRoute));
    n += sizeof(gRoute);
    memcpy(raw + n, gFoot, sizeof(gFoot));
    n += sizeof(gFoot);
    raw[n++] = static_cast<uint8_t>(gJointEn & 0xFF);
    raw[n++] = static_cast<uint8_t>(gJointEn >> 8);
    raw[n++] = gFootEn;
    portEXIT_CRITICAL(&gLock);
    usbSend(kUsbProf, raw, static_cast<uint16_t>(n));
}

static void sendMap(int joint) {
    if (joint < 0 || joint >= kCoreJoints) {
        UsbMapErr err{};
        err.ch = static_cast<int8_t>(joint);
        err.reason = kUsbReasonBadCh;
        usbSend(kUsbMapErr, &err, sizeof(err));
        return;
    }
    CalMap map;
    portENTER_CRITICAL(&gMapLock);
    map = gCal[joint];
    portEXIT_CRITICAL(&gMapLock);
    const int total = map.ok ? map.count : 0;
    int start = 0;
    do {
        const int remain = total - start;
        const int n = total == 0 ? 0 : (remain < static_cast<int>(kUsbMapChunkLen) ? remain : static_cast<int>(kUsbMapChunkLen));
        uint8_t raw[sizeof(UsbMapChunkHdr) + sizeof(UsbMapPoint) * kUsbMapChunkLen];
        UsbMapChunkHdr hdr{};
        hdr.ch = static_cast<uint8_t>(joint);
        hdr.total = static_cast<uint16_t>(total);
        hdr.start = static_cast<uint16_t>(start);
        hdr.n = static_cast<uint8_t>(n);
        memcpy(raw, &hdr, sizeof(hdr));
        for (int i = 0; i < n; ++i) {
            UsbMapPoint pt{map.x[start + i], map.y[start + i]};
            memcpy(raw + sizeof(hdr) + sizeof(pt) * static_cast<size_t>(i), &pt, sizeof(pt));
        }
        usbSend(kUsbMapChunk, raw, static_cast<uint16_t>(sizeof(hdr) + sizeof(UsbMapPoint) * static_cast<size_t>(n)));
        start += n;
    } while (start < total);
    if (total == 0) {
        return;
    }
}

static void acceptMapChunk(const uint8_t* payload, uint16_t len) {
    if (len < sizeof(UsbMapChunkHdr)) {
        return;
    }
    UsbMapChunkHdr hdr{};
    memcpy(&hdr, payload, sizeof(hdr));
    if (hdr.ch >= kCoreJoints || hdr.n > kUsbMapChunkLen || hdr.total > kMapLen) {
        UsbMapErr err{};
        err.ch = static_cast<int8_t>(hdr.ch);
        err.reason = kUsbReasonBadArg;
        usbSend(kUsbMapErr, &err, sizeof(err));
        return;
    }
    const size_t need = sizeof(hdr) + sizeof(UsbMapPoint) * hdr.n;
    if (len < need) {
        return;
    }
    if (hdr.start == 0) {
        gMapRx.joint = hdr.ch;
        gMapRx.total = hdr.total;
        gMapRx.got = 0;
    }
    if (gMapRx.joint != hdr.ch || hdr.start != gMapRx.got) {
        UsbMapErr err{};
        err.ch = static_cast<int8_t>(hdr.ch);
        err.got = static_cast<uint16_t>(gMapRx.got);
        err.expect = hdr.start;
        err.reason = kUsbReasonMap;
        usbSend(kUsbMapErr, &err, sizeof(err));
        return;
    }
    for (int i = 0; i < hdr.n; ++i) {
        UsbMapPoint pt{};
        memcpy(&pt, payload + sizeof(hdr) + sizeof(pt) * static_cast<size_t>(i), sizeof(pt));
        gMapRx.x[gMapRx.got] = pt.x;
        gMapRx.y[gMapRx.got] = pt.y;
        ++gMapRx.got;
    }
    if (gMapRx.got < gMapRx.total) {
        return;
    }
    if (gMapRx.total < 2) {
        UsbMapErr err{};
        err.ch = static_cast<int8_t>(hdr.ch);
        err.reason = kUsbReasonCount;
        usbSend(kUsbMapErr, &err, sizeof(err));
        return;
    }
    portENTER_CRITICAL(&gMapLock);
    gCal[hdr.ch].ok = true;
    gCal[hdr.ch].count = gMapRx.total;
    memcpy(gCal[hdr.ch].x, gMapRx.x, sizeof(float) * static_cast<size_t>(gMapRx.total));
    memcpy(gCal[hdr.ch].y, gMapRx.y, sizeof(float) * static_cast<size_t>(gMapRx.total));
    portEXIT_CRITICAL(&gMapLock);
    const bool saved = saveCal(hdr.ch);
    if (!saved) {
        UsbMapErr err{};
        err.ch = static_cast<int8_t>(hdr.ch);
        err.reason = kUsbReasonNvs;
        usbSend(kUsbMapErr, &err, sizeof(err));
        return;
    }
    UsbMapOk ok{};
    ok.ch = hdr.ch;
    ok.count = static_cast<uint16_t>(gMapRx.total);
    usbSend(kUsbMapOk, &ok, sizeof(ok));
}

static void acceptProfile(const uint8_t* payload, uint16_t len) {
    // n + 10 routes + 2 feet + joint_en u16 + foot_en u8
    const size_t need = 1 + sizeof(JointRoute) * kCoreJoints + sizeof(FootRoute) * kCoreFeet + 3;
    if (len < 1 || payload[0] != kCoreJoints || len != need) {
        uint8_t reason = kUsbReasonCount;
        usbSend(kUsbProfErr, &reason, 1);
        return;
    }
    portENTER_CRITICAL(&gLock);
    memcpy(gRoute, payload + 1, sizeof(gRoute));
    memcpy(gFoot, payload + 1 + sizeof(gRoute), sizeof(gFoot));
    const size_t enAt = 1 + sizeof(gRoute) + sizeof(gFoot);
    gJointEn = static_cast<uint16_t>(payload[enAt] | (static_cast<uint16_t>(payload[enAt + 1]) << 8));
    gFootEn = payload[enAt + 2];
    portEXIT_CRITICAL(&gLock);
    for (int i = 0; i < kCoreJoints; ++i) {
        gInaReady[i] = false;
    }
    if (!saveProfile()) {
        uint8_t reason = kUsbReasonNvs;
        usbSend(kUsbProfErr, &reason, 1);
        return;
    }
    UsbProfOk ok{};
    ok.n = kCoreJoints;
    ok.is_default = 0;
    usbSend(kUsbProfOk, &ok, sizeof(ok));
}

static void setMode(WorkMode mode) {
    gMode = mode;
    if (mode == WorkMode::Robot) {
        gOutMask = static_cast<uint16_t>((1u << kCoreJoints) - 1u);
        for (int i = 0; i < kCoreJoints; ++i) {
            gCmd[i] = kHoldDeg;
        }
    } else {
        gOutMask = 0;
    }
    sendMode();
}

static void onCommand(uint8_t type, const uint8_t* payload, uint16_t len) {
    switch (type) {
        case kUsbCmdPing:
            sendHello();
            break;
        case kUsbCmdScan:
            gScanReq = 1;
            break;
        case kUsbCmdIdentify:
            gIdentifyReq = 1;
            break;
        case kUsbCmdHold:
            for (int i = 0; i < kCoreJoints; ++i) {
                gCmd[i] = kHoldDeg;
            }
            sendMode();
            break;
        case kUsbCmdMode:
            if (len >= sizeof(UsbCmdMode)) {
                UsbCmdMode c{};
                memcpy(&c, payload, sizeof(c));
                setMode(c.mode ? WorkMode::Robot : WorkMode::Lab);
            }
            break;
        case kUsbCmdOut:
            if (len >= sizeof(UsbCmdOut)) {
                UsbCmdOut c{};
                memcpy(&c, payload, sizeof(c));
                if (c.ch == 0xFF) {
                    gOutMask = c.on ? static_cast<uint16_t>((1u << kCoreJoints) - 1u) : 0;
                } else if (c.ch < kCoreJoints) {
                    if (c.on) {
                        gOutMask = static_cast<uint16_t>(gOutMask | (1u << c.ch));
                    } else {
                        gOutMask = static_cast<uint16_t>(gOutMask & ~(1u << c.ch));
                    }
                }
                sendMode();
            }
            break;
        case kUsbCmdJoint:
            if (len >= sizeof(UsbCmdJoint)) {
                UsbCmdJoint c{};
                memcpy(&c, payload, sizeof(c));
                if (c.ch < kCoreJoints) {
                    gCmd[c.ch] = clampMove(c.deg);
                }
            }
            break;
        case kUsbCmdProfGet:
            sendProfile();
            break;
        case kUsbCmdProfDefault: {
            // 制御タスクが経路をコピーしている間に途中の値を見せない。
            JointRoute routes[kCoreJoints];
            FootRoute feet[kCoreFeet];
            fillDefaultTopology(routes, feet);
            portENTER_CRITICAL(&gLock);
            memcpy(gRoute, routes, sizeof(gRoute));
            memcpy(gFoot, feet, sizeof(gFoot));
            gJointEn = 0x03FF;
            gFootEn = 0x03;
            portEXIT_CRITICAL(&gLock);
            saveProfile();
            {
                UsbProfOk ok{};
                ok.n = kCoreJoints;
                ok.is_default = 1;
                usbSend(kUsbProfOk, &ok, sizeof(ok));
            }
            sendProfile();
            break;
        }
        case kUsbCmdProfPut:
            acceptProfile(payload, len);
            break;
        case kUsbCmdMapGet:
            if (len >= sizeof(UsbCmdMapGet)) {
                UsbCmdMapGet c{};
                memcpy(&c, payload, sizeof(c));
                sendMap(c.ch);
            }
            break;
        case kUsbCmdMapChunk:
            acceptMapChunk(payload, len);
            break;
        default:
            break;
    }
}

static uint8_t gRx[1024];
static size_t gRxLen = 0;

static void usbFeed(const uint8_t* data, size_t n) {
    if (gRxLen + n > sizeof(gRx)) {
        gRxLen = 0;
    }
    memcpy(gRx + gRxLen, data, n);
    gRxLen += n;
    while (gRxLen >= kUsbFrameOverhead) {
        size_t start = 0;
        while (start + 1 < gRxLen && !(gRx[start] == kUsbMagic0 && gRx[start + 1] == kUsbMagic1)) {
            ++start;
        }
        if (start > 0) {
            memmove(gRx, gRx + start, gRxLen - start);
            gRxLen -= start;
        }
        if (gRxLen < kUsbFrameOverhead) {
            return;
        }
        const uint16_t len = static_cast<uint16_t>(gRx[3] | (static_cast<uint16_t>(gRx[4]) << 8));
        if (len > kUsbMaxPayload) {
            memmove(gRx, gRx + 1, gRxLen - 1);
            --gRxLen;
            continue;
        }
        const size_t total = static_cast<size_t>(kUsbFrameOverhead) + len;
        if (gRxLen < total) {
            return;
        }
        const uint16_t crcGot = static_cast<uint16_t>(gRx[5 + len] | (static_cast<uint16_t>(gRx[6 + len]) << 8));
        if (usbCrc16(gRx + 2, static_cast<size_t>(3) + len) != crcGot) {
            memmove(gRx, gRx + 1, gRxLen - 1);
            --gRxLen;
            continue;
        }
        onCommand(gRx[2], gRx + 5, len);
        memmove(gRx, gRx + total, gRxLen - total);
        gRxLen -= total;
    }
}

static void usbTask(void*) {
    uint32_t next = micros();
    for (;;) {
        while (Serial.available() > 0) {
            uint8_t b = static_cast<uint8_t>(Serial.read());
            usbFeed(&b, 1);
        }
        if (gScanReady) {
            gScanReady = 0;
            uint8_t n = static_cast<uint8_t>(gScanCount);
            usbSend(kUsbScanBegin, &n, 1);
            for (int i = 0; i < gScanCount; ++i) {
                usbSend(kUsbScanNode, &gScan[i], sizeof(UsbScanNode));
            }
            usbSend(kUsbScanEnd, nullptr, 0);
        }
        if (gIdentifyReq) {
            gIdentifyReq = 0;
            usbSend(kUsbIdentifyOk, nullptr, 0);
        }
        if (gEvtOver) {
            gEvtOver = 0;
            UsbEvtOc ev{gOverAmp};
            usbSend(kUsbEvtOc, &ev, sizeof(ev));
        }
        const uint32_t now = micros();
        if (static_cast<int32_t>(now - next) >= 0) {
            sendTelemetry();
            next = now + kPeriodUs;
        }
        vTaskDelay(pdMS_TO_TICKS(2));
    }
}

static void controlTask(void*) {
    uint32_t prev = micros();
    uint32_t seq = 0;
    for (;;) {
        const uint32_t t0 = micros();
        if (gScanReq) {
            gScanReq = 0;
            runScan();
        }
        const uint32_t tSense0 = micros();
        Snapshot snap{};
        readSensors(snap);
        const uint32_t tSense1 = micros();
        for (int i = 0; i < kCoreJoints; ++i) {
            snap.cmd_deg[i] = gCmd[i];
            snap.map_ok[i] = 0;
            snap.corr_deg[i] = NAN;
            if (!snap.as_ok[i]) {
                continue;
            }
            portENTER_CRITICAL(&gMapLock);
            const float corr = interpMap(gCal[i], snap.unwrap_deg[i]);
            snap.map_ok[i] = gCal[i].ok ? 1 : 0;
            portEXIT_CRITICAL(&gMapLock);
            snap.corr_deg[i] = corr;
        }
        const uint32_t tState = micros();
        const uint32_t tAct0 = micros();
        writeServos();
        const uint32_t tAct1 = micros();
        const uint32_t t1 = tAct1;
        snap.seq = seq++;
        snap.t_period_us = t0 - prev;
        snap.t_loop_us = t1 - t0;
        snap.t_sense_us = tSense1 - tSense0;
        snap.t_state_us = tState - tSense1;
        snap.t_policy_us = 0;
        snap.t_act_us = tAct1 - tAct0;
        snap.jitter_us = static_cast<int32_t>(snap.t_period_us) - static_cast<int32_t>(kPeriodUs);
        snap.overrun = snap.t_loop_us > kPeriodUs ? 1 : 0;
        snap.i2c_err = gI2cErr;
        snap.servo_ok = gServoReady ? 1 : 0;
        snap.mode = static_cast<uint8_t>(gMode);
        snap.out_mask = gOutMask;
        portENTER_CRITICAL(&gLock);
        gSnap = snap;
        portEXIT_CRITICAL(&gLock);
        prev = t0;
        const uint32_t spent = micros() - t0;
        if (spent < kPeriodUs) {
            vTaskDelay(pdMS_TO_TICKS((kPeriodUs - spent) / 1000));
        } else {
            taskYIELD();
        }
    }
}

void setup() {
    Serial.begin(115200);
    Serial.setTxBufferSize(4096);
    Serial.setTxTimeoutMs(20);
    usbHoldRebootOff();
    delay(200);

    for (int i = 0; i < kCoreJoints; ++i) {
        gCmd[i] = kHoldDeg;
    }
    gMapRx.joint = -1;
    loadProfile();
    loadCal();
    gAs5600.begin(kSdaPin, kSclPin, kI2cHz);
    closeAllHubs();
    initServos();
    closeAllHubs();

    xTaskCreatePinnedToCore(controlTask, "rt", kRtStack, nullptr, 3, nullptr, kRtCore);
    xTaskCreatePinnedToCore(usbTask, "usb", kUsbStack, nullptr, 2, nullptr, kUsbCore);
}

void loop() {
    vTaskDelay(pdMS_TO_TICKS(1000));
}
