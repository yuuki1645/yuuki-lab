/**
 * リアルタイム制御ファーム（環境 rt-usb）
 *
 * ATOMS3 Lite を制御中枢とし、開発中の通信は USB のみ（Wi-Fi なし）。
 *
 * Core 1: 20 Hz 制御ループ
 *   センサ取得 → 状態生成（空）→ RL/テスト指令（空）→ 関節制御 → サーボ
 * Core 0: スナップショットと診断を USB 送信する（I2C は触らない）
 *
 * 配線の典型（機体）:
 *   Grove I2C → PaHub 0x70（軸 N = CHN の AS5600）
 *   PaHub 0x71 の INA226（既定は CH0/CH1。関節プロファイルで 8 枠まで）
 *   Unit 8Servos 0x25 は Hub 手前
 * 机上では挿抜自由。SCAN で実際の接続を返す。
 *
 * 作業モード:
 *   Lab（既定）  PWM は明示するまで出さない。机上向け。
 *   Robot        全軸出力オン。Hold 135°（従来の rt_monitor 向け）。
 *
 * USB はバイナリフレーム（usb_proto.hpp）。改行 CSV は使わない。
 */

#include <Arduino.h>
#include <FastLED.h>
#include <M5_UNIT_8SERVO.h>
#include <Preferences.h>
#include <freertos/FreeRTOS.h>
#include <freertos/portmacro.h>
#include <freertos/task.h>
#include <math.h>
#include <string.h>

#include "as5600.hpp"
#include "ina226.hpp"
#include "joint_profile.hpp"
#include "pahub.hpp"
#include "snapshot.hpp"
#include "usb_proto.hpp"

// ---------------------------------------------------------------------------
// ハードウェア / 周期
// ---------------------------------------------------------------------------
static constexpr int kPinLed = 35;
static constexpr int kPinButton = 41;
static constexpr int kPinSda = 2;
static constexpr int kPinScl = 1;
static constexpr int kNumLeds = 1;
static constexpr uint8_t kLedBrightness = 48;

static constexpr int kHubChServo = -1;  // 互換用。経路は gProf を正とする
static constexpr uint8_t kHubAddress = PaHub::kDefaultAddress;
static constexpr int kInaCount = kSnapIna;

static constexpr int kJointCount = kSnapJoints;

static constexpr float kServoFullMinDeg = 0.0f;
static constexpr float kServoFullMaxDeg = 270.0f;
static constexpr uint16_t kPulseMinUs = 500;
static constexpr uint16_t kPulseMaxUs = 2500;
static constexpr float kMoveMinDeg = 40.0f;
static constexpr float kMoveMaxDeg = 230.0f;
static constexpr float kHoldDeg = 135.0f;
/** 机上の過電流で PWM を落とす閾値（10A ユニット想定） */
static constexpr float kOvercurrentAmp = 8.0f;

static constexpr uint32_t kPeriodMs = 50;
static constexpr uint32_t kPeriodUs = kPeriodMs * 1000;
static constexpr int kMapLen = 191;
static constexpr int kFwVer = kUsbFwVer;
static constexpr float kSweepStepDeg = 1.0f;
static constexpr uint32_t kSettleMinMs = 100;
static constexpr uint32_t kSettleMaxMs = 700;
static constexpr uint32_t kFirstMoveMinMs = 600;
static constexpr uint32_t kFirstMoveMaxMs = 2500;
static constexpr uint32_t kPostSettleMs = 40;
static constexpr float kSettleEpsDeg = 0.15f;
static constexpr int kSettleStableCount = 4;
static constexpr int kAvgReads = 5;
static constexpr int kMaxCalSamples = 400;

static constexpr int kRtCore = 1;
static constexpr int kUsbCore = 0;
static constexpr uint32_t kRtStack = 10240;
static constexpr uint32_t kUsbStack = 6144;

static constexpr int kMaxScanNodes = 48;
static constexpr uint32_t kIdentifyMs = 2500;
static constexpr uint32_t kButtonDebounceMs = 40;

// ---------------------------------------------------------------------------
// 状態
// ---------------------------------------------------------------------------
struct SensorFrame {
    float raw_deg[kJointCount];
    float unwrapped[kJointCount];
    bool as5600_ok[kJointCount];
    uint8_t mag_code[kJointCount];
    uint8_t agc[kJointCount];
    float ina_volt[kInaCount];
    float ina_amp[kInaCount];
    float ina_watt[kInaCount];
    bool ina_ok[kInaCount];
};

struct RobotState {
    float q[kJointCount];
    float corr[kJointCount];
    bool q_ok[kJointCount];
    bool map_ok[kJointCount];
    float power_w[kInaCount];
};

struct CalMap {
    bool ok;
    int count;
    float x[kMapLen];
    float y[kMapLen];
};

struct Action {
    float cmd_deg[kJointCount];
};

/** I2C スキャン 1 ノード。hub=0 は Grove 直結 */
struct ScanNode {
    uint8_t hub;
    int8_t ch;
    uint8_t addr;
    uint8_t kind;      // 0 unknown, 1 pahub, 2 as5600, 3 ina226, 4 servo
    uint8_t mag_code;  // AS5600 以外は 255
    uint8_t agc;
};

enum ScanKind : uint8_t {
    kKindUnknown = 0,
    kKindPahub = 1,
    kKindAs5600 = 2,
    kKindIna = 3,
    kKindServo = 4,
};

// ---------------------------------------------------------------------------
// デバイス
// ---------------------------------------------------------------------------
static CRGB gLeds[kNumLeds];
static As5600 gAs5600;
static Ina226 gIna226[kInaCount];
static bool gInaPresent[kInaCount] = {};
static bool gEncAlive[kJointCount] = {};
static void resetEncAlive();
static M5_UNIT_8SERVO gServo;
static bool gServoOk = false;
static PaHub gHub(kHubAddress);
/** 0x70〜0x77 のうち、閉じる対象。既定は本機の 0x70+0x71。スキャンで更新する */
static uint8_t gHubSeenMask = 0x03;

static float gUnwrapPrev[kJointCount];
static float gUnwrapped[kJointCount];
static bool gUnwrapInited[kJointCount];

static Action gLastAction;
static CalMap gCal[kJointCount];
static Preferences gPrefs;
static portMUX_TYPE gMapLock = portMUX_INITIALIZER_UNLOCKED;
static portMUX_TYPE gCmdLock = portMUX_INITIALIZER_UNLOCKED;
static portMUX_TYPE gProfLock = portMUX_INITIALIZER_UNLOCKED;

/** 論理関節 → 物理経路。NVS "jprof" または既定値 */
static JointRoute gProf[kJointCount];

/** USB 受信の組み立て（マジック待ち → type/len → payload → CRC） */
enum UsbRxState : uint8_t {
    kUsbRxMagic0 = 0,
    kUsbRxMagic1,
    kUsbRxType,
    kUsbRxLen0,
    kUsbRxLen1,
    kUsbRxPayload,
    kUsbRxCrc0,
    kUsbRxCrc1,
};
static uint8_t gRxState = kUsbRxMagic0;
static uint8_t gRxType = 0;
static uint16_t gRxLen = 0;
static uint16_t gRxGot = 0;
static uint8_t gRxPayload[kUsbMaxPayload];
static uint8_t gRxCrcLo = 0;

static bool gMapRxActive = false;
static int gMapRxCh = 0;
static int gMapRxExpect = 0;
static int gMapRxCount = 0;
static float gMapRxX[kMapLen];
static float gMapRxY[kMapLen];
static volatile int gMapDumpCh = -1;
static uint32_t gMapRxLastMs = 0;

static volatile uint8_t gProfDumpReq = 0;
static JointRoute gProfRx[kJointCount];

static portMUX_TYPE gSnapLock = portMUX_INITIALIZER_UNLOCKED;
static Snapshot gSnapFront;
static volatile bool gSnapReady = false;

static volatile WorkMode gMode = WorkMode::Lab;
static volatile uint8_t gOutMask = 0;
static volatile uint32_t gIdentifyUntilMs = 0;
static volatile uint8_t gScanReq = 0;    // 1=要求
static volatile uint8_t gScanReady = 0;  // 1=結果あり
static volatile uint8_t gHelloReq = 0;
static volatile uint8_t gEvtOvercurrent = 0;
static volatile uint8_t gEvtBtn = 0;
static volatile uint16_t gI2cErr = 0;
static volatile float gOverAmp = 0.0f;

static float gManualCmd[kJointCount];
static ScanNode gScanNodes[kMaxScanNodes];
static int gScanCount = 0;
static bool gHaveScan = false;

static uint8_t gProbeHub = 0;
static int gProbeCh = 0;
static volatile uint8_t gProbeReq = 0;  // 1=root addr, 2=hub ch
static UsbProbe gProbeResult;
static volatile uint8_t gProbeReady = 0;

/** 校正要求。-1=なし、0..=関節番号。Core0 が立て、Core1 が実行 */
static volatile int gCalReq = -1;
static volatile uint8_t gCalAbort = 0;
static volatile uint8_t gCalibrating = 0;
static volatile uint8_t gCalMsgReady = 0;
static uint8_t gCalMsgType = 0;
static uint8_t gCalPayload[16];
static uint8_t gCalPayloadLen = 0;

static float gCalX[kMaxCalSamples];
static float gCalY[kMaxCalSamples];
static int gCalSampleCount = 0;
static float gCalScale = 1.0f;
static float gCalOffset = 0.0f;
static float gCalRms = 0.0f;
static float gCalMaxAbs = 0.0f;

// ---------------------------------------------------------------------------
// ユーティリティ
// ---------------------------------------------------------------------------
static float clampMoveDeg(float deg) {
    if (deg < kMoveMinDeg) {
        return kMoveMinDeg;
    }
    if (deg > kMoveMaxDeg) {
        return kMoveMaxDeg;
    }
    return deg;
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

static float unwrapJoint(int i, float rawDeg) {
    if (!gUnwrapInited[i]) {
        gUnwrapPrev[i] = rawDeg;
        gUnwrapped[i] = rawDeg;
        gUnwrapInited[i] = true;
        return gUnwrapped[i];
    }
    gUnwrapped[i] += shortestDelta(gUnwrapPrev[i], rawDeg);
    gUnwrapPrev[i] = rawDeg;
    return gUnwrapped[i];
}

static String calKey(const char* prefix, int ch) {
    return String(prefix) + String(ch);
}

static float lookupMap(int ch, float as5600Unwrapped) {
    if (ch < 0 || ch >= kJointCount) {
        return as5600Unwrapped;
    }
    portENTER_CRITICAL(&gMapLock);
    const bool ok = gCal[ch].ok && gCal[ch].count >= 2;
    const int n = gCal[ch].count;
    if (!ok) {
        portEXIT_CRITICAL(&gMapLock);
        return as5600Unwrapped;
    }
    if (as5600Unwrapped <= gCal[ch].x[0]) {
        const float y = gCal[ch].y[0];
        portEXIT_CRITICAL(&gMapLock);
        return y;
    }
    if (as5600Unwrapped >= gCal[ch].x[n - 1]) {
        const float y = gCal[ch].y[n - 1];
        portEXIT_CRITICAL(&gMapLock);
        return y;
    }
    for (int i = 0; i < n - 1; ++i) {
        const float x0 = gCal[ch].x[i];
        const float x1 = gCal[ch].x[i + 1];
        if (as5600Unwrapped >= x0 && as5600Unwrapped <= x1) {
            const float den = x1 - x0;
            float y = gCal[ch].y[i];
            if (fabsf(den) >= 1e-4f) {
                const float t = (as5600Unwrapped - x0) / den;
                y += t * (gCal[ch].y[i + 1] - gCal[ch].y[i]);
            }
            portEXIT_CRITICAL(&gMapLock);
            return y;
        }
    }
    portEXIT_CRITICAL(&gMapLock);
    return as5600Unwrapped;
}

static void loadCalibration(int ch) {
    if (ch < 0 || ch >= kJointCount) {
        return;
    }
    gPrefs.begin("cal", true);
    CalMap tmp;
    memset(&tmp, 0, sizeof(tmp));
    tmp.count = gPrefs.getInt(calKey("mn", ch).c_str(), 0);
    tmp.ok = gPrefs.getBool(calKey("mk", ch).c_str(), false) && tmp.count >= 8;
    if (tmp.ok && tmp.count <= kMapLen) {
        const size_t bytes = static_cast<size_t>(tmp.count) * sizeof(float);
        if (gPrefs.getBytes(calKey("mx", ch).c_str(), tmp.x, bytes) != bytes ||
            gPrefs.getBytes(calKey("my", ch).c_str(), tmp.y, bytes) != bytes) {
            tmp.ok = false;
            tmp.count = 0;
        }
    } else {
        tmp.ok = false;
        tmp.count = 0;
    }
    gPrefs.end();
    portENTER_CRITICAL(&gMapLock);
    gCal[ch] = tmp;
    portEXIT_CRITICAL(&gMapLock);
}

static bool saveCalibration(int ch) {
    if (ch < 0 || ch >= kJointCount) {
        return false;
    }
    CalMap tmp;
    portENTER_CRITICAL(&gMapLock);
    tmp = gCal[ch];
    portEXIT_CRITICAL(&gMapLock);
    gPrefs.begin("cal", false);
    gPrefs.putBool(calKey("ok", ch).c_str(), tmp.ok);
    gPrefs.putBool(calKey("mk", ch).c_str(), tmp.ok);
    gPrefs.putInt(calKey("mn", ch).c_str(), tmp.count);
    bool wrote = true;
    if (tmp.count > 0) {
        const size_t bytes = static_cast<size_t>(tmp.count) * sizeof(float);
        if (gPrefs.putBytes(calKey("mx", ch).c_str(), tmp.x, bytes) != bytes ||
            gPrefs.putBytes(calKey("my", ch).c_str(), tmp.y, bytes) != bytes) {
            wrote = false;
        }
    }
    gPrefs.end();
    return wrote;
}

static uint16_t angleToPulse(float angleDeg) {
    angleDeg = clampMoveDeg(angleDeg);
    const float t = (angleDeg - kServoFullMinDeg) /
                    (kServoFullMaxDeg - kServoFullMinDeg);
    const float us = kPulseMinUs + t * static_cast<float>(kPulseMaxUs - kPulseMinUs);
    return static_cast<uint16_t>(us + 0.5f);
}

static void setLed(uint8_t r, uint8_t g, uint8_t b) {
    gLeds[0] = CRGB(r, g, b);
    FastLED.show();
}

/** 既定プロファイル。サーボは 8 軸、AS5600 は PaHub 6 ch、INA は先頭 kProfInaDefaultCount 軸。 */
static void fillDefaultProfile(JointRoute* out) {
    for (int i = 0; i < kJointCount; ++i) {
        out[i].act_hub = 0;
        out[i].act_ch = -1;
        out[i].act_addr = kProfActAddrDefault;
        out[i].servo_ch = static_cast<uint8_t>(i);
        if (i < PaHub::kChannelCount) {
            out[i].enc_hub = kProfAsHubDefault;
            out[i].enc_ch = static_cast<int8_t>(i);
            out[i].enc_addr = kProfEncAddrDefault;
        } else {
            out[i].enc_hub = 0;
            out[i].enc_ch = -1;
            out[i].enc_addr = 0;
        }
        // 未配線の INA を毎周期ポーリングしないよう、既定は先頭 2 軸だけ
        if (i < kProfInaDefaultCount && i < kInaCount) {
            out[i].ina_hub = kProfInaHubDefault;
            out[i].ina_ch = static_cast<int8_t>(i);
            out[i].ina_addr = kProfInaAddrDefault;
        } else {
            out[i].ina_hub = 0;
            out[i].ina_ch = -1;
            out[i].ina_addr = 0;
        }
    }
}

static void copyProfile(JointRoute* dst, const JointRoute* src) {
    memcpy(dst, src, sizeof(JointRoute) * static_cast<size_t>(kJointCount));
}

static bool validateRoute(const JointRoute& r) {
    // enc_addr==0 はエンコーダ未接続。Hub 経路は見ない
    if (r.enc_addr != 0 && r.enc_hub != 0) {
        if (r.enc_hub < 0x70 || r.enc_hub > 0x77) {
            return false;
        }
        if (r.enc_ch < 0 || r.enc_ch >= PaHub::kChannelCount) {
            return false;
        }
    }
    if (r.act_hub != 0) {
        if (r.act_hub < 0x70 || r.act_hub > 0x77) {
            return false;
        }
        if (r.act_ch < 0 || r.act_ch >= PaHub::kChannelCount) {
            return false;
        }
    }
    if (r.servo_ch > 7) {
        return false;
    }
    // ina_addr==0 は未割当。それ以外は enc と同じ Hub 規則
    if (r.ina_addr != 0) {
        if (r.ina_hub != 0) {
            if (r.ina_hub < 0x70 || r.ina_hub > 0x77) {
                return false;
            }
            if (r.ina_ch < 0 || r.ina_ch >= PaHub::kChannelCount) {
                return false;
            }
        }
    }
    return true;
}

static bool validateProfile(const JointRoute* p) {
    for (int i = 0; i < kJointCount; ++i) {
        if (!validateRoute(p[i])) {
            return false;
        }
    }
    return true;
}

static void loadProfile() {
    JointRoute tmp[kJointCount];
    fillDefaultProfile(tmp);
    gPrefs.begin("jprof", true);
    const int n = gPrefs.getInt("n", 0);
    bool ok = (n == kJointCount);
    if (ok) {
        const size_t bytes = sizeof(tmp);
        if (gPrefs.getBytes("r", tmp, bytes) != bytes || !validateProfile(tmp)) {
            ok = false;
            fillDefaultProfile(tmp);
        }
    }
    gPrefs.end();
    portENTER_CRITICAL(&gProfLock);
    copyProfile(gProf, tmp);
    portEXIT_CRITICAL(&gProfLock);
    resetEncAlive();
}

static bool saveProfile() {
    JointRoute tmp[kJointCount];
    portENTER_CRITICAL(&gProfLock);
    copyProfile(tmp, gProf);
    portEXIT_CRITICAL(&gProfLock);
    if (!validateProfile(tmp)) {
        return false;
    }
    gPrefs.begin("jprof", false);
    gPrefs.putInt("n", kJointCount);
    const size_t bytes = sizeof(tmp);
    const bool wrote = gPrefs.putBytes("r", tmp, bytes) == bytes;
    gPrefs.end();
    return wrote;
}

static void applyDefaultProfile() {
    JointRoute tmp[kJointCount];
    fillDefaultProfile(tmp);
    portENTER_CRITICAL(&gProfLock);
    copyProfile(gProf, tmp);
    portEXIT_CRITICAL(&gProfLock);
    resetEncAlive();
}

static void markHubSeen(uint8_t addr) {
    if (addr < 0x70 || addr > 0x77) {
        return;
    }
    gHubSeenMask = static_cast<uint8_t>(gHubSeenMask | (1u << (addr - 0x70)));
}

/**
 * 既知の全 PaHub を全 CH オフ。ping 成功時だけ閉じると、衝突中に閉じ漏れする。
 * 未接続アドレスへの write は NACK で即戻る（タイムアウト待ちではない）。
 */
static void closeAllHubs() {
    for (uint8_t a = 0x70; a <= 0x77; ++a) {
        if ((gHubSeenMask & (1u << (a - 0x70))) == 0) {
            continue;
        }
        PaHub h(a);
        h.select(-1);
    }
}

/**
 * MUX 経路を開く。他 Hub の CH が残っていると 0x36/0x41 が親バスで衝突するので、
 * 先に全 Hub を閉じてから目的の 1 CH だけ開く。hub==0 は直結（全 MUX オフのみ）。
 */
static void openMux(uint8_t hub, int8_t ch) {
    closeAllHubs();
    if (hub == 0) {
        return;
    }
    markHubSeen(hub);
    PaHub h(hub);
    h.select(static_cast<int>(ch));
}

static void closeMux(uint8_t hub) {
    (void)hub;
    closeAllHubs();
}

static JointRoute jointRoute(int joint) {
    JointRoute r;
    portENTER_CRITICAL(&gProfLock);
    r = gProf[joint];
    portEXIT_CRITICAL(&gProfLock);
    return r;
}

/** 未接続エンコーダを毎周期タイムアウトしないよう、読む対象を付け直す。 */
static void resetEncAlive() {
    for (int i = 0; i < kJointCount; ++i) {
        gEncAlive[i] = (jointRoute(i).enc_addr != 0);
    }
}

static bool i2cPing(uint8_t addr) {
    Wire.beginTransmission(addr);
    return Wire.endTransmission() == 0;
}

static uint8_t kindFromAddr(uint8_t addr) {
    if (addr >= 0x70 && addr <= 0x77) {
        return kKindPahub;
    }
    if (addr == As5600::kI2cAddress) {
        return kKindAs5600;
    }
    if (addr == Ina226::kI2cAddress || addr == 0x40) {
        return kKindIna;
    }
    if (addr == 0x25) {
        return kKindServo;
    }
    return kKindUnknown;
}

static uint8_t allOutMask() {
    return static_cast<uint8_t>((1u << kJointCount) - 1u);
}

static void addScanNode(uint8_t hub, int8_t ch, uint8_t addr, uint8_t kind,
                         uint8_t magCode, uint8_t agc) {
    if (gScanCount >= kMaxScanNodes) {
        return;
    }
    ScanNode& n = gScanNodes[gScanCount++];
    n.hub = hub;
    n.ch = ch;
    n.addr = addr;
    n.kind = kind;
    n.mag_code = magCode;
    n.agc = agc;
}

static void readAs5600Extras(uint8_t& magCode, uint8_t& agc) {
    const As5600::MagnetStatus st = gAs5600.readMagnetStatus();
    magCode = As5600::statusToCode(st);
    if (!gAs5600.readAgc(agc)) {
        agc = 255;
    }
}

/** 既知アドレス。Hub 先はフルスキャンすると遅いのでこれに限る */
static const uint8_t kHubProbeAddr[] = {
    0x25, 0x36, 0x38, 0x3C, 0x40, 0x41, 0x44, 0x48, 0x5D, 0x60, 0x62, 0x68,
};

/**
 * I2C トポロジを取る。制御コア専用。1 回で数百 ms になり得る。
 */
static void runI2cScan() {
    const uint32_t oldTimeout = 3;
    Wire.setTimeOut(oldTimeout);
    gScanCount = 0;
    closeAllHubs();
    delayMicroseconds(400);

    uint8_t rootHit[128];
    memset(rootHit, 0, sizeof(rootHit));

    for (uint8_t a = 0x08; a <= 0x77; ++a) {
        if (!i2cPing(a)) {
            continue;
        }
        rootHit[a] = 1;
        uint8_t mag = 255;
        uint8_t agc = 255;
        const uint8_t kind = kindFromAddr(a);
        if (kind == kKindAs5600) {
            readAs5600Extras(mag, agc);
        }
        addScanNode(0, -1, a, kind, mag, agc);
    }

    uint8_t foundHubs = 0;
    for (uint8_t a = 0x70; a <= 0x77; ++a) {
        if (rootHit[a]) {
            foundHubs = static_cast<uint8_t>(foundHubs | (1u << (a - 0x70)));
        }
    }
    if (foundHubs != 0) {
        gHubSeenMask = foundHubs;
    }

    for (uint8_t hub = 0x70; hub <= 0x77; ++hub) {
        if (!rootHit[hub]) {
            continue;
        }
        PaHub h(hub);
        for (int ch = 0; ch < PaHub::kChannelCount; ++ch) {
            closeAllHubs();
            h.select(ch);
            delayMicroseconds(400);
            for (size_t i = 0; i < sizeof(kHubProbeAddr); ++i) {
                const uint8_t a = kHubProbeAddr[i];
                if (rootHit[a]) {
                    continue;
                }
                if (!i2cPing(a)) {
                    continue;
                }
                uint8_t mag = 255;
                uint8_t agc = 255;
                const uint8_t kind = kindFromAddr(a);
                if (kind == kKindAs5600) {
                    readAs5600Extras(mag, agc);
                }
                addScanNode(hub, static_cast<int8_t>(ch), a, kind, mag, agc);
            }
        }
        closeAllHubs();
    }

    Wire.setTimeOut(20);
    gHaveScan = true;
    resetEncAlive();

    // ホットプラグ: スキャン結果と関節プロファイルの INA 経路を照合
    bool sawServo = false;
    bool sawIna[kInaCount] = {};
    for (int i = 0; i < gScanCount; ++i) {
        const ScanNode& n = gScanNodes[i];
        if (n.kind == kKindServo) {
            sawServo = true;
        }
        if (n.kind != kKindIna) {
            continue;
        }
        for (int k = 0; k < kJointCount; ++k) {
            const JointRoute r = jointRoute(k);
            if (r.ina_addr == 0) {
                continue;
            }
            const bool hubOk = (r.ina_hub == 0) ? (n.hub == 0)
                                                : (n.hub == r.ina_hub && n.ch == r.ina_ch);
            if (hubOk && n.addr == r.ina_addr && k < kInaCount) {
                sawIna[k] = true;
            }
        }
    }
    if (sawServo && !gServoOk) {
        // プロファイル上のアクチュエータ経路で初期化を試みる
        const JointRoute r0 = jointRoute(0);
        openMux(r0.act_hub, r0.act_ch);
        gServoOk = gServo.begin(&Wire, kPinSda, kPinScl, r0.act_addr);
        Wire.setClock(100000);
        Wire.setTimeOut(20);
        if (gServoOk) {
            for (int i = 0; i < kJointCount; ++i) {
                const JointRoute ri = jointRoute(i);
                openMux(ri.act_hub, ri.act_ch);
                gServo.setOnePinMode(ri.servo_ch, SERVO_CTL_MODE);
                closeMux(ri.act_hub);
            }
        }
        closeMux(r0.act_hub);
    }
    if (!sawServo) {
        gServoOk = false;
    }
    for (int k = 0; k < kInaCount; ++k) {
        if (sawIna[k] && !gInaPresent[k]) {
            const JointRoute r = jointRoute(k);
            gIna226[k].setAddress(r.ina_addr);
            openMux(r.ina_hub, r.ina_ch);
            delay(3);
            gInaPresent[k] = gIna226[k].isConnected() && gIna226[k].begin();
            closeMux(r.ina_hub);
        }
        if (!sawIna[k]) {
            gInaPresent[k] = false;
        }
    }
}

static void probeClear(UsbProbe& p) {
    memset(&p, 0, sizeof(p));
}

static void runProbeRoot(uint8_t addr) {
    closeAllHubs();
    delayMicroseconds(400);
    probeClear(gProbeResult);
    gProbeResult.hub = 0;
    gProbeResult.ch = -1;
    gProbeResult.addr = addr;
    if (!i2cPing(addr)) {
        return;
    }
    const uint8_t kind = kindFromAddr(addr);
    if (kind == kKindAs5600) {
        float deg = 0.0f;
        uint8_t mag = 255;
        uint8_t agc = 255;
        uint16_t magnitude = 0;
        const As5600::MagnetStatus st = gAs5600.readMagnetStatus();
        mag = As5600::statusToCode(st);
        gAs5600.readAgc(agc);
        gAs5600.readMagnitude(magnitude);
        const bool ok = gAs5600.readDegrees(deg);
        gProbeResult.found = kKindAs5600;
        gProbeResult.f0 = deg;
        gProbeResult.mag = mag;
        gProbeResult.agc = agc;
        gProbeResult.magnitude = magnitude;
        gProbeResult.ok = ok ? 1 : 0;
        return;
    }
    if (kind == kKindIna) {
        Ina226 tmp;
        tmp.begin();
        float v = 0.0f, a = 0.0f, w = 0.0f;
        const uint8_t ok = tmp.read(v, a, w) ? 1 : 0;
        gProbeResult.found = kKindIna;
        gProbeResult.f0 = v;
        gProbeResult.f1 = a;
        gProbeResult.f2 = w;
        gProbeResult.ok = ok;
        return;
    }
}

static void runProbeHub(uint8_t hub, int ch) {
    closeAllHubs();
    markHubSeen(hub);
    PaHub h(hub);
    h.select(ch);
    delayMicroseconds(400);
    probeClear(gProbeResult);
    gProbeResult.hub = hub;
    gProbeResult.ch = static_cast<int8_t>(ch);
    if (i2cPing(As5600::kI2cAddress)) {
        float deg = 0.0f;
        uint8_t agc = 255;
        uint16_t magnitude = 0;
        const As5600::MagnetStatus st = gAs5600.readMagnetStatus();
        gAs5600.readAgc(agc);
        gAs5600.readMagnitude(magnitude);
        const bool ok = gAs5600.readDegrees(deg);
        gProbeResult.found = kKindAs5600;
        gProbeResult.addr = As5600::kI2cAddress;
        gProbeResult.f0 = deg;
        gProbeResult.mag = As5600::statusToCode(st);
        gProbeResult.agc = agc;
        gProbeResult.magnitude = magnitude;
        gProbeResult.ok = ok ? 1 : 0;
        closeAllHubs();
        return;
    }
    if (i2cPing(Ina226::kI2cAddress)) {
        Ina226 tmp;
        tmp.begin();
        float v = 0.0f, a = 0.0f, w = 0.0f;
        const uint8_t ok = tmp.read(v, a, w) ? 1 : 0;
        gProbeResult.found = kKindIna;
        gProbeResult.addr = Ina226::kI2cAddress;
        gProbeResult.f0 = v;
        gProbeResult.f1 = a;
        gProbeResult.f2 = w;
        gProbeResult.ok = ok;
        closeAllHubs();
        return;
    }
    closeAllHubs();
}

// ---------------------------------------------------------------------------
// センサ / 状態 / 政策 / 関節（制御コア専用。I2C はここだけ）
// ---------------------------------------------------------------------------
static void readSensors(SensorFrame& out) {
    memset(&out, 0, sizeof(out));

    for (int i = 0; i < kJointCount; ++i) {
        out.mag_code[i] = 255;
        out.agc[i] = 255;
        const JointRoute route = jointRoute(i);
        if (route.enc_addr == 0 || !gEncAlive[i]) {
            out.as5600_ok[i] = false;
            out.raw_deg[i] = NAN;
            out.unwrapped[i] = NAN;
            continue;
        }
        openMux(route.enc_hub, route.enc_ch);
        delayMicroseconds(300);
        const As5600::MagnetStatus st = gAs5600.readMagnetStatus();
        out.mag_code[i] = As5600::statusToCode(st);
        uint8_t agc = 255;
        if (st != As5600::MagnetStatus::CommError) {
            gAs5600.readAgc(agc);
        }
        out.agc[i] = agc;
        if (st == As5600::MagnetStatus::Ok && gAs5600.readDegrees(out.raw_deg[i])) {
            out.as5600_ok[i] = true;
            out.unwrapped[i] = unwrapJoint(i, out.raw_deg[i]);
        } else {
            out.as5600_ok[i] = false;
            out.raw_deg[i] = NAN;
            out.unwrapped[i] = NAN;
            ++gI2cErr;
            if (st == As5600::MagnetStatus::CommError) {
                gEncAlive[i] = false;
            }
        }
        closeMux(route.enc_hub);
    }

    for (int i = 0; i < kInaCount; ++i) {
        const JointRoute route = jointRoute(i);
        if (route.ina_addr == 0) {
            out.ina_ok[i] = false;
            out.ina_volt[i] = NAN;
            out.ina_amp[i] = NAN;
            out.ina_watt[i] = NAN;
            continue;
        }
        gIna226[i].setAddress(route.ina_addr);
        openMux(route.ina_hub, route.ina_ch);
        delayMicroseconds(300);
        if (!gInaPresent[i]) {
            gInaPresent[i] = gIna226[i].isConnected() && gIna226[i].begin();
        }
        if (gInaPresent[i] && gIna226[i].read(out.ina_volt[i], out.ina_amp[i], out.ina_watt[i])) {
            out.ina_ok[i] = true;
            if (fabsf(out.ina_amp[i]) > kOvercurrentAmp) {
                gOutMask = 0;
                gOverAmp = out.ina_amp[i];
                gEvtOvercurrent = 1;
            }
        } else {
            gInaPresent[i] = false;
            out.ina_ok[i] = false;
            out.ina_volt[i] = NAN;
            out.ina_amp[i] = NAN;
            out.ina_watt[i] = NAN;
            ++gI2cErr;
        }
        closeMux(route.ina_hub);
    }
}

static void buildState(const SensorFrame& sense, RobotState& state) {
    for (int i = 0; i < kJointCount; ++i) {
        state.q_ok[i] = sense.as5600_ok[i];
        if (!sense.as5600_ok[i] || isnan(sense.unwrapped[i])) {
            state.corr[i] = NAN;
            state.q[i] = NAN;
            state.map_ok[i] = false;
            continue;
        }
        const float corr = lookupMap(i, sense.unwrapped[i]);
        state.corr[i] = corr;
        state.q[i] = corr;
        portENTER_CRITICAL(&gMapLock);
        state.map_ok[i] = gCal[i].ok;
        portEXIT_CRITICAL(&gMapLock);
    }
    for (int i = 0; i < kInaCount; ++i) {
        state.power_w[i] = sense.ina_watt[i];
    }
}

static void selectAction(const RobotState& /*state*/, Action& action) {
    if (gMode == WorkMode::Robot) {
        for (int i = 0; i < kJointCount; ++i) {
            action.cmd_deg[i] = kHoldDeg;
        }
        return;
    }
    portENTER_CRITICAL(&gCmdLock);
    for (int i = 0; i < kJointCount; ++i) {
        action.cmd_deg[i] = gManualCmd[i];
    }
    portEXIT_CRITICAL(&gCmdLock);
}

static void applyJoints(const Action& action) {
    if (!gServoOk) {
        return;
    }
    const uint8_t mask = gOutMask;
    if (mask == 0) {
        return;
    }
    for (int i = 0; i < kJointCount; ++i) {
        if ((mask & (1u << i)) == 0) {
            continue;
        }
        if (isnan(action.cmd_deg[i])) {
            continue;
        }
        const JointRoute route = jointRoute(i);
        openMux(route.act_hub, route.act_ch);
        delayMicroseconds(200);
        const uint16_t pulse = angleToPulse(action.cmd_deg[i]);
        gServo.setServoPulse(route.servo_ch, pulse);
        closeMux(route.act_hub);
    }
}

// ---------------------------------------------------------------------------
// 校正スイープ（atoms3 robot と同じ方針。関節プロファイルの経路を使う）
// ---------------------------------------------------------------------------
static void calPush(uint8_t type, const void* payload, uint8_t len) {
    uint32_t t0 = millis();
    while (gCalMsgReady && (millis() - t0) < 300) {
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    gCalMsgType = type;
    gCalPayloadLen = len < sizeof(gCalPayload) ? len : sizeof(gCalPayload);
    if (payload != nullptr && gCalPayloadLen > 0) {
        memcpy(gCalPayload, payload, gCalPayloadLen);
    }
    gCalMsgReady = 1;
}

static void calPushStart(uint8_t ch) {
    UsbCalStart p{};
    p.ch = ch;
    calPush(kUsbCalStart, &p, sizeof(p));
}

static void calPushProg(uint8_t ch, uint8_t pct, float cmd) {
    UsbCalProg p{};
    p.ch = ch;
    p.pct = pct;
    p.cmd = cmd;
    calPush(kUsbCalProg, &p, sizeof(p));
}

static void calPushOk(uint8_t ch, uint16_t count, float rms, float maxAbs) {
    UsbCalOk p{};
    p.ch = ch;
    p.count = count;
    p.rms = rms;
    p.max_abs = maxAbs;
    calPush(kUsbCalOk, &p, sizeof(p));
}

static void calPushErr(int8_t ch, uint8_t reason) {
    UsbCalErr p{};
    p.ch = ch;
    p.reason = reason;
    calPush(kUsbCalErr, &p, sizeof(p));
}

static bool calAborted() {
    return gCalAbort != 0;
}

static bool calCommandServo(int joint, float angleDeg) {
    if (!gServoOk || joint < 0 || joint >= kJointCount) {
        return false;
    }
    const JointRoute route = jointRoute(joint);
    openMux(route.act_hub, route.act_ch);
    delayMicroseconds(200);
    const uint16_t pulse = angleToPulse(angleDeg);
    const bool ok = gServo.setServoPulse(route.servo_ch, pulse);
    closeMux(route.act_hub);
    return ok;
}

static bool calReadRaw(int joint, float& rawDeg) {
    const JointRoute route = jointRoute(joint);
    openMux(route.enc_hub, route.enc_ch);
    delayMicroseconds(300);
    if (gAs5600.readMagnetStatus() != As5600::MagnetStatus::Ok) {
        closeMux(route.enc_hub);
        return false;
    }
    const bool ok = gAs5600.readDegrees(rawDeg);
    closeMux(route.enc_hub);
    return ok;
}

static bool calReadAveraged(int joint, float& rawDeg) {
    float sum = 0.0f;
    int n = 0;
    for (int i = 0; i < kAvgReads; ++i) {
        float v = 0.0f;
        if (calReadRaw(joint, v)) {
            sum += v;
            ++n;
        }
        delay(4);
    }
    if (n == 0) {
        return false;
    }
    rawDeg = sum / static_cast<float>(n);
    return true;
}

static bool calWaitSettled(int joint, uint32_t minMs, uint32_t maxMs) {
    delay(minMs);
    float prev = 0.0f;
    if (!calReadRaw(joint, prev)) {
        return false;
    }
    unwrapJoint(joint, prev);

    int stable = 0;
    const uint32_t start = millis();
    while ((millis() - start) < maxMs) {
        if (calAborted()) {
            return false;
        }
        delay(20);
        float cur = 0.0f;
        if (!calReadRaw(joint, cur)) {
            return false;
        }
        unwrapJoint(joint, cur);
        if (fabsf(shortestDelta(prev, cur)) < kSettleEpsDeg) {
            ++stable;
            if (stable >= kSettleStableCount) {
                delay(kPostSettleMs);
                return true;
            }
        } else {
            stable = 0;
        }
        prev = cur;
    }
    delay(kPostSettleMs);
    return true;
}

static bool calAddSample(float as5600Unwrapped, float servoCmd) {
    if (gCalSampleCount >= kMaxCalSamples) {
        return false;
    }
    gCalX[gCalSampleCount] = as5600Unwrapped;
    gCalY[gCalSampleCount] = servoCmd;
    ++gCalSampleCount;
    return true;
}

static bool calFitLinear() {
    if (gCalSampleCount < 8) {
        return false;
    }
    double sx = 0, sy = 0, sxx = 0, sxy = 0;
    const double n = static_cast<double>(gCalSampleCount);
    for (int i = 0; i < gCalSampleCount; ++i) {
        const double x = gCalX[i];
        const double y = gCalY[i];
        sx += x;
        sy += y;
        sxx += x * x;
        sxy += x * y;
    }
    const double denom = n * sxx - sx * sx;
    if (fabs(denom) < 1e-6) {
        return false;
    }
    gCalScale = static_cast<float>((n * sxy - sx * sy) / denom);
    gCalOffset = static_cast<float>((sy - static_cast<double>(gCalScale) * sx) / n);

    float xmin = gCalX[0];
    float xmax = gCalX[0];
    for (int i = 1; i < gCalSampleCount; ++i) {
        if (gCalX[i] < xmin) {
            xmin = gCalX[i];
        }
        if (gCalX[i] > xmax) {
            xmax = gCalX[i];
        }
    }
    if ((xmax - xmin) < 40.0f) {
        return false;
    }
    if (fabsf(gCalScale) < 0.3f || fabsf(gCalScale) > 3.0f) {
        return false;
    }
    return true;
}

static void calSortMap(CalMap& m) {
    for (int i = 1; i < m.count; ++i) {
        const float x = m.x[i];
        const float y = m.y[i];
        int j = i - 1;
        while (j >= 0 && m.x[j] > x) {
            m.x[j + 1] = m.x[j];
            m.y[j + 1] = m.y[j];
            --j;
        }
        m.x[j + 1] = x;
        m.y[j + 1] = y;
    }
}

static float calLookupTmp(const CalMap& m, float as5600Unwrapped) {
    if (!m.ok || m.count < 2) {
        return gCalScale * as5600Unwrapped + gCalOffset;
    }
    if (as5600Unwrapped <= m.x[0]) {
        return m.y[0];
    }
    if (as5600Unwrapped >= m.x[m.count - 1]) {
        return m.y[m.count - 1];
    }
    for (int i = 0; i < m.count - 1; ++i) {
        const float x0 = m.x[i];
        const float x1 = m.x[i + 1];
        if (as5600Unwrapped >= x0 && as5600Unwrapped <= x1) {
            const float den = x1 - x0;
            if (fabsf(den) < 1e-4f) {
                return m.y[i];
            }
            const float t = (as5600Unwrapped - x0) / den;
            return m.y[i] + t * (m.y[i + 1] - m.y[i]);
        }
    }
    return gCalScale * as5600Unwrapped + gCalOffset;
}

static bool calBuildMap(CalMap& out) {
    float sum[kMapLen];
    int cnt[kMapLen];
    for (int i = 0; i < kMapLen; ++i) {
        sum[i] = 0.0f;
        cnt[i] = 0;
    }
    for (int i = 0; i < gCalSampleCount; ++i) {
        const int idx = static_cast<int>(gCalY[i] + 0.5f) - static_cast<int>(kMoveMinDeg);
        if (idx < 0 || idx >= kMapLen) {
            continue;
        }
        sum[idx] += gCalX[i];
        ++cnt[idx];
    }
    memset(&out, 0, sizeof(out));
    for (int i = 0; i < kMapLen; ++i) {
        if (cnt[i] == 0) {
            continue;
        }
        out.x[out.count] = sum[i] / static_cast<float>(cnt[i]);
        out.y[out.count] = kMoveMinDeg + static_cast<float>(i);
        ++out.count;
    }
    calSortMap(out);
    if (out.count < 80) {
        return false;
    }
    out.ok = true;
    double sse = 0;
    gCalMaxAbs = 0.0f;
    for (int i = 0; i < gCalSampleCount; ++i) {
        const float pred = calLookupTmp(out, gCalX[i]);
        const float err = pred - gCalY[i];
        sse += static_cast<double>(err) * static_cast<double>(err);
        const float aerr = fabsf(err);
        if (aerr > gCalMaxAbs) {
            gCalMaxAbs = aerr;
        }
    }
    gCalRms = static_cast<float>(sqrt(sse / static_cast<double>(gCalSampleCount)));
    return true;
}

static bool calSweepCollect(int joint, float startDeg, float endDeg, int passIndex) {
    const float dir = (endDeg >= startDeg) ? 1.0f : -1.0f;
    const float span = fabsf(endDeg - startDeg);
    const int steps = static_cast<int>(span / kSweepStepDeg + 0.5f);
    for (int i = 0; i <= steps; ++i) {
        if (calAborted()) {
            return false;
        }
        float cmd = startDeg + dir * kSweepStepDeg * static_cast<float>(i);
        if (dir > 0.0f && cmd > endDeg) {
            cmd = endDeg;
        }
        if (dir < 0.0f && cmd < endDeg) {
            cmd = endDeg;
        }
        cmd = clampMoveDeg(cmd);
        calCommandServo(joint, cmd);
        if (!calWaitSettled(joint, kSettleMinMs, kSettleMaxMs)) {
            calPushErr(static_cast<int8_t>(joint), kUsbReasonSettle);
            return false;
        }
        float raw = 0.0f;
        if (!calReadAveraged(joint, raw)) {
            calPushErr(static_cast<int8_t>(joint), kUsbReasonAs5600);
            return false;
        }
        const float unwrapped = unwrapJoint(joint, raw);
        if (!calAddSample(unwrapped, cmd)) {
            calPushErr(static_cast<int8_t>(joint), kUsbReasonFull);
            return false;
        }
        // 往復 2 パス分を 0..100 にマップ
        const int total = (steps + 1) * 2;
        const int done = passIndex * (steps + 1) + i + 1;
        const int pct = (total > 0) ? (done * 100 / total) : 100;
        if ((i % 5) == 0 || i == steps) {
            calPushProg(static_cast<uint8_t>(joint), static_cast<uint8_t>(pct), cmd);
        }
        {
            const uint8_t hue = static_cast<uint8_t>(cmd * (255.0f / 270.0f));
            const CRGB c = CHSV(hue, 255, 160);
            setLed(c.r, c.g, c.b);
        }
    }
    return true;
}

/**
 * 関節 joint を 40→230→40 で掃引し、1° マップを NVS に保存する。
 * 制御コア専用（I2C + delay）。完了後 gMapDumpCh でマップ送出を依頼。
 */
static void runCalibration(int joint) {
    if (joint < 0 || joint >= kJointCount) {
        calPushErr(static_cast<int8_t>(joint), kUsbReasonBadCh);
        return;
    }
    if (!gServoOk) {
        calPushErr(static_cast<int8_t>(joint), kUsbReasonServo);
        return;
    }

    gCalibrating = 1;
    gCalAbort = 0;
    gCalSampleCount = 0;
    gUnwrapInited[joint] = false;

    const uint8_t prevMask = gOutMask;
    gOutMask = static_cast<uint8_t>(prevMask | (1u << joint));

    calPushStart(static_cast<uint8_t>(joint));
    setLed(255, 160, 0);

    calCommandServo(joint, kMoveMinDeg);
    if (calAborted() || !calWaitSettled(joint, kFirstMoveMinMs, kFirstMoveMaxMs)) {
        gOutMask = prevMask;
        gCalibrating = 0;
        calPushErr(static_cast<int8_t>(joint), calAborted() ? kUsbReasonAbort : kUsbReasonFirst);
        setLed(180, 0, 0);
        return;
    }

    if (!calSweepCollect(joint, kMoveMinDeg, kMoveMaxDeg, 0) ||
        !calSweepCollect(joint, kMoveMaxDeg, kMoveMinDeg, 1)) {
        calCommandServo(joint, kHoldDeg);
        gOutMask = prevMask;
        gCalibrating = 0;
        if (calAborted()) {
            calPushErr(static_cast<int8_t>(joint), kUsbReasonAbort);
        }
        setLed(180, 0, 0);
        return;
    }

    calCommandServo(joint, kHoldDeg);
    delay(400);

    if (!calFitLinear()) {
        gOutMask = prevMask;
        gCalibrating = 0;
        calPushErr(static_cast<int8_t>(joint), kUsbReasonFit);
        setLed(180, 0, 0);
        return;
    }

    CalMap built;
    if (!calBuildMap(built)) {
        gOutMask = prevMask;
        gCalibrating = 0;
        calPushErr(static_cast<int8_t>(joint), kUsbReasonMap);
        setLed(180, 0, 0);
        return;
    }

    portENTER_CRITICAL(&gMapLock);
    gCal[joint] = built;
    portEXIT_CRITICAL(&gMapLock);
    if (!saveCalibration(joint)) {
        gOutMask = prevMask;
        gCalibrating = 0;
        calPushErr(static_cast<int8_t>(joint), kUsbReasonNvs);
        setLed(180, 0, 0);
        return;
    }

    portENTER_CRITICAL(&gCmdLock);
    gManualCmd[joint] = kHoldDeg;
    portEXIT_CRITICAL(&gCmdLock);
    gOutMask = prevMask;
    gCalibrating = 0;
    calPushOk(static_cast<uint8_t>(joint), static_cast<uint16_t>(built.count), gCalRms, gCalMaxAbs);
    gMapDumpCh = joint;
    setLed(0, 180, 40);
}

static void publishSnapshot(const Snapshot& snap) {
    portENTER_CRITICAL(&gSnapLock);
    gSnapFront = snap;
    gSnapReady = true;
    portEXIT_CRITICAL(&gSnapLock);
}

static bool copySnapshot(Snapshot& out) {
    portENTER_CRITICAL(&gSnapLock);
    const bool ready = gSnapReady;
    if (ready) {
        out = gSnapFront;
    }
    portEXIT_CRITICAL(&gSnapLock);
    return ready;
}

static void fillSnapshot(Snapshot& snap,
                         uint32_t seq,
                         uint32_t t_period_us,
                         uint32_t t_sense_us,
                         uint32_t t_state_us,
                         uint32_t t_policy_us,
                         uint32_t t_act_us,
                         uint32_t t_loop_us,
                         const SensorFrame& sense,
                         const RobotState& state,
                         const Action& action) {
    snap.seq = seq;
    snap.t_period_us = t_period_us;
    snap.t_loop_us = t_loop_us;
    snap.t_sense_us = t_sense_us;
    snap.t_state_us = t_state_us;
    snap.t_policy_us = t_policy_us;
    snap.t_act_us = t_act_us;
    snap.jitter_us = static_cast<int32_t>(t_period_us) - static_cast<int32_t>(kPeriodUs);
    snap.overrun = (t_loop_us > kPeriodUs) ? 1 : 0;

    for (int i = 0; i < kJointCount; ++i) {
        snap.cmd_deg[i] = action.cmd_deg[i];
        snap.as5600_raw[i] = sense.raw_deg[i];
        snap.as5600_unwrapped[i] = sense.unwrapped[i];
        snap.as5600_corr[i] = state.corr[i];
        snap.as5600_ok[i] = sense.as5600_ok[i] ? 1 : 0;
        snap.map_ok[i] = state.map_ok[i] ? 1 : 0;
        snap.mag_code[i] = sense.mag_code[i];
        snap.agc[i] = sense.agc[i];
    }
    for (int i = 0; i < kInaCount; ++i) {
        snap.ina_volt[i] = sense.ina_volt[i];
        snap.ina_amp[i] = sense.ina_amp[i];
        snap.ina_watt[i] = sense.ina_watt[i];
        snap.ina_ok[i] = sense.ina_ok[i] ? 1 : 0;
    }
    snap.i2c_err = gI2cErr;
    snap.servo_ok = gServoOk ? 1 : 0;
    snap.mode = static_cast<uint8_t>(gMode);
    snap.out_mask = gOutMask;
}

// ---------------------------------------------------------------------------
// USB（Core 0）
// ---------------------------------------------------------------------------
/** 1 フレームをバッファに組んでから、できるだけ 1 回の write で出す。 */
static void usbSend(uint8_t type, const void* payload, uint16_t len) {
    uint8_t buf[kUsbFrameOverhead + kUsbMaxPayload];
    const size_t n = usbBuildFrame(buf, sizeof(buf), type, payload, len);
    if (n == 0) {
        return;
    }
    const uint32_t t0 = millis();
    while (Serial.availableForWrite() < static_cast<int>(n)) {
        if ((millis() - t0) > 80) {
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    Serial.write(buf, n);
}

static void usbPrintHello() {
    UsbHello h{};
    h.ver = static_cast<uint8_t>(kFwVer);
    h.mode = static_cast<uint8_t>(gMode);
    h.joints = static_cast<uint8_t>(kJointCount);
    h.ina = static_cast<uint8_t>(kInaCount);
    h.servo = gServoOk ? 1 : 0;
    h.out_mask = gOutMask;
    usbSend(kUsbHello, &h, sizeof(h));
}

static void usbDumpProfile() {
    JointRoute tmp[kJointCount];
    portENTER_CRITICAL(&gProfLock);
    copyProfile(tmp, gProf);
    portEXIT_CRITICAL(&gProfLock);
    uint8_t raw[1 + sizeof(JointRoute) * kJointCount];
    raw[0] = static_cast<uint8_t>(kJointCount);
    memcpy(raw + 1, tmp, sizeof(tmp));
    usbSend(kUsbProf, raw, static_cast<uint16_t>(sizeof(raw)));
}

static void profSendErr(uint8_t reason) {
    usbSend(kUsbProfErr, &reason, 1);
}

static void usbDumpScan() {
    const uint8_t n = static_cast<uint8_t>(gScanCount);
    usbSend(kUsbScanBegin, &n, 1);
    for (int i = 0; i < gScanCount; ++i) {
        const ScanNode& nd = gScanNodes[i];
        UsbScanNode p{};
        p.hub = nd.hub;
        p.ch = nd.ch;
        p.addr = nd.addr;
        p.kind = nd.kind;
        p.mag = nd.mag_code;
        p.agc = nd.agc;
        usbSend(kUsbScanNode, &p, sizeof(p));
    }
    usbSend(kUsbScanEnd, nullptr, 0);
}

static void usbPrintFrame(const Snapshot& s) {
    UsbTelemetry t{};
    t.seq = s.seq;
    t.t_period_us = s.t_period_us;
    t.t_loop_us = s.t_loop_us;
    t.t_sense_us = s.t_sense_us;
    t.t_state_us = s.t_state_us;
    t.t_policy_us = s.t_policy_us;
    t.t_act_us = s.t_act_us;
    t.jitter_us = s.jitter_us;
    t.overrun = s.overrun;
    for (int i = 0; i < kJointCount; ++i) {
        t.cmd_deg[i] = s.cmd_deg[i];
        t.raw_deg[i] = s.as5600_raw[i];
        t.unwrap_deg[i] = s.as5600_unwrapped[i];
        t.corr_deg[i] = s.as5600_corr[i];
        t.as_ok[i] = s.as5600_ok[i];
        t.map_ok[i] = s.map_ok[i];
        t.mag[i] = s.mag_code[i];
        t.agc[i] = s.agc[i];
    }
    for (int i = 0; i < kInaCount; ++i) {
        t.volt[i] = s.ina_ok[i] ? s.ina_volt[i] : 0.0f;
        t.amp[i] = s.ina_ok[i] ? s.ina_amp[i] : 0.0f;
        t.watt[i] = s.ina_ok[i] ? s.ina_watt[i] : 0.0f;
        t.ina_ok[i] = s.ina_ok[i];
    }
    t.i2c_err = s.i2c_err;
    t.servo_ok = s.servo_ok;
    t.mode = s.mode;
    t.out_mask = s.out_mask;
    usbSend(kUsbTelemetry, &t, static_cast<uint16_t>(sizeof(t)));
}

static void usbDumpMap(int ch) {
    if (ch < 0 || ch >= kJointCount) {
        return;
    }
    CalMap tmp;
    portENTER_CRITICAL(&gMapLock);
    tmp = gCal[ch];
    portEXIT_CRITICAL(&gMapLock);

    uint8_t raw[sizeof(UsbMapChunkHdr) + kUsbMapChunkLen * sizeof(UsbMapPoint)];
    const int total = tmp.count;
    if (total <= 0) {
        UsbMapChunkHdr h{};
        h.ch = static_cast<uint8_t>(ch);
        usbSend(kUsbMapChunk, &h, sizeof(h));
        return;
    }
    int start = 0;
    while (start < total) {
        const int n = (total - start > kUsbMapChunkLen) ? kUsbMapChunkLen : (total - start);
        UsbMapChunkHdr* hdr = reinterpret_cast<UsbMapChunkHdr*>(raw);
        hdr->ch = static_cast<uint8_t>(ch);
        hdr->total = static_cast<uint16_t>(total);
        hdr->start = static_cast<uint16_t>(start);
        hdr->n = static_cast<uint8_t>(n);
        UsbMapPoint* pts = reinterpret_cast<UsbMapPoint*>(raw + sizeof(UsbMapChunkHdr));
        for (int i = 0; i < n; ++i) {
            pts[i].x = tmp.x[start + i];
            pts[i].y = tmp.y[start + i];
        }
        usbSend(kUsbMapChunk, raw,
                static_cast<uint16_t>(sizeof(UsbMapChunkHdr) +
                                     static_cast<size_t>(n) * sizeof(UsbMapPoint)));
        start += n;
    }
}

static void mapRxFail(uint8_t reason) {
    UsbMapErr e{};
    e.ch = static_cast<int8_t>(gMapRxCh);
    e.got = static_cast<uint16_t>(gMapRxCount);
    e.expect = static_cast<uint16_t>(gMapRxExpect);
    e.reason = reason;
    gMapRxActive = false;
    usbSend(kUsbMapErr, &e, sizeof(e));
}

static void mapRxCommit() {
    if (!gMapRxActive) {
        return;
    }
    if (gMapRxCount < 8) {
        mapRxFail(kUsbReasonShort);
        return;
    }
    const int ch = gMapRxCh;
    const int npts = gMapRxCount;
    CalMap tmp;
    memset(&tmp, 0, sizeof(tmp));
    tmp.count = npts;
    tmp.ok = true;
    for (int i = 0; i < npts; ++i) {
        tmp.x[i] = gMapRxX[i];
        tmp.y[i] = gMapRxY[i];
    }
    gMapRxActive = false;
    portENTER_CRITICAL(&gMapLock);
    gCal[ch] = tmp;
    portEXIT_CRITICAL(&gMapLock);
    if (!saveCalibration(ch)) {
        mapRxFail(kUsbReasonNvs);
        return;
    }
    UsbMapOk ok{};
    ok.ch = static_cast<uint8_t>(ch);
    ok.count = static_cast<uint16_t>(tmp.count);
    usbSend(kUsbMapOk, &ok, sizeof(ok));
}

static void ackModeOut() {
    UsbModeOut m{};
    m.mode = static_cast<uint8_t>(gMode);
    m.out_mask = gOutMask;
    usbSend(kUsbMode, &m, sizeof(m));
}

static void applyHold() {
    if (gCalibrating) {
        gCalAbort = 1;
    }
    if (gMode == WorkMode::Lab) {
        gOutMask = 0;
    } else {
        gOutMask = allOutMask();
        portENTER_CRITICAL(&gCmdLock);
        for (int i = 0; i < kJointCount; ++i) {
            gManualCmd[i] = kHoldDeg;
        }
        portEXIT_CRITICAL(&gCmdLock);
    }
    ackModeOut();
}

static void handleUsbFrame(uint8_t type, const uint8_t* p, uint16_t len) {
    // PC からの 1 フレーム。CRC 通過後にだけ来る。
    if (type == kUsbCmdPing) {
        gHelloReq = 1;
        if (!gHaveScan) {
            gScanReq = 1;
        } else {
            gScanReady = 1;
        }
        return;
    }
    if (type == kUsbCmdScan) {
        gScanReq = 1;
        return;
    }
    if (type == kUsbCmdIdentify) {
        gIdentifyUntilMs = millis() + kIdentifyMs;
        usbSend(kUsbIdentifyOk, nullptr, 0);
        return;
    }
    if (type == kUsbCmdHold) {
        applyHold();
        return;
    }
    if (type == kUsbCmdCalAbort) {
        gCalAbort = 1;
        calPushErr(-1, kUsbReasonAbort);
        return;
    }
    if (type == kUsbCmdCal && len >= sizeof(UsbCmdCal)) {
        UsbCmdCal c{};
        memcpy(&c, p, sizeof(c));
        if (c.ch >= kJointCount) {
            calPushErr(static_cast<int8_t>(c.ch), kUsbReasonBadCh);
            return;
        }
        if (gCalibrating || gCalReq >= 0) {
            calPushErr(static_cast<int8_t>(c.ch), kUsbReasonBusy);
            return;
        }
        gCalAbort = 0;
        gCalReq = c.ch;
        return;
    }
    if (type == kUsbCmdMode && len >= sizeof(UsbCmdMode)) {
        UsbCmdMode c{};
        memcpy(&c, p, sizeof(c));
        if (c.mode != 0) {
            gMode = WorkMode::Robot;
            gOutMask = allOutMask();
            portENTER_CRITICAL(&gCmdLock);
            for (int i = 0; i < kJointCount; ++i) {
                gManualCmd[i] = kHoldDeg;
            }
            portEXIT_CRITICAL(&gCmdLock);
        } else {
            gMode = WorkMode::Lab;
            gOutMask = 0;
        }
        ackModeOut();
        return;
    }
    if (type == kUsbCmdOut && len >= sizeof(UsbCmdOut)) {
        UsbCmdOut c{};
        memcpy(&c, p, sizeof(c));
        if (c.ch == 0xFF) {
            gOutMask = (c.on != 0) ? allOutMask() : 0;
        } else if (c.ch < kJointCount) {
            if (c.on != 0) {
                gOutMask = static_cast<uint8_t>(gOutMask | (1u << c.ch));
            } else {
                gOutMask = static_cast<uint8_t>(gOutMask & ~(1u << c.ch));
            }
        }
        ackModeOut();
        return;
    }
    if (type == kUsbCmdJoint && len >= sizeof(UsbCmdJoint)) {
        UsbCmdJoint c{};
        memcpy(&c, p, sizeof(c));
        if (c.ch < kJointCount) {
            portENTER_CRITICAL(&gCmdLock);
            gManualCmd[c.ch] = clampMoveDeg(c.deg);
            portEXIT_CRITICAL(&gCmdLock);
        }
        return;
    }
    if (type == kUsbCmdProbe && len >= sizeof(UsbCmdProbe)) {
        UsbCmdProbe c{};
        memcpy(&c, p, sizeof(c));
        if (c.hub_mode == 0) {
            gProbeHub = 0;
            gProbeCh = c.hub_or_addr;
            gProbeReq = 1;
        } else {
            gProbeHub = c.hub_or_addr;
            gProbeCh = c.ch;
            gProbeReq = 2;
        }
        return;
    }
    if (type == kUsbCmdProfGet) {
        gProfDumpReq = 1;
        return;
    }
    if (type == kUsbCmdProfDefault) {
        applyDefaultProfile();
        for (int i = 0; i < kInaCount; ++i) {
            gInaPresent[i] = false;
        }
        if (!saveProfile()) {
            profSendErr(kUsbReasonNvs);
            return;
        }
        UsbProfOk ok{};
        ok.n = static_cast<uint8_t>(kJointCount);
        ok.is_default = 1;
        usbSend(kUsbProfOk, &ok, sizeof(ok));
        gProfDumpReq = 1;
        return;
    }
    if (type == kUsbCmdProfPut) {
        if (len < 1) {
            profSendErr(kUsbReasonBadArg);
            return;
        }
        const uint8_t n = p[0];
        if (n != kJointCount || len != static_cast<uint16_t>(1 + n * sizeof(JointRoute))) {
            profSendErr(kUsbReasonCount);
            return;
        }
        memcpy(gProfRx, p + 1, sizeof(gProfRx));
        if (!validateProfile(gProfRx)) {
            profSendErr(kUsbReasonBad);
            return;
        }
        portENTER_CRITICAL(&gProfLock);
        copyProfile(gProf, gProfRx);
        portEXIT_CRITICAL(&gProfLock);
        resetEncAlive();
        for (int i = 0; i < kInaCount; ++i) {
            gInaPresent[i] = false;
        }
        if (!saveProfile()) {
            profSendErr(kUsbReasonNvs);
            return;
        }
        UsbProfOk ok{};
        ok.n = n;
        ok.is_default = 0;
        usbSend(kUsbProfOk, &ok, sizeof(ok));
        return;
    }
    if (type == kUsbCmdMapGet && len >= sizeof(UsbCmdMapGet)) {
        UsbCmdMapGet c{};
        memcpy(&c, p, sizeof(c));
        int ch = c.ch;
        if (ch < 0 || ch >= kJointCount) {
            ch = 0;
        }
        gMapDumpCh = ch;
        return;
    }
    if (type == kUsbCmdMapChunk && len >= sizeof(UsbMapChunkHdr)) {
        UsbMapChunkHdr h{};
        memcpy(&h, p, sizeof(h));
        if (h.ch >= kJointCount || h.n > kUsbMapChunkLen) {
            gMapRxCh = h.ch;
            gMapRxCount = 0;
            gMapRxExpect = h.total;
            mapRxFail(kUsbReasonBadArg);
            return;
        }
        const size_t need = sizeof(UsbMapChunkHdr) + static_cast<size_t>(h.n) * sizeof(UsbMapPoint);
        if (len < need) {
            mapRxFail(kUsbReasonBadArg);
            return;
        }
        if (h.start == 0) {
            if (h.total < 2 || h.total > kMapLen) {
                gMapRxCh = h.ch;
                gMapRxExpect = h.total;
                gMapRxCount = 0;
                mapRxFail(kUsbReasonBadArg);
                return;
            }
            gMapRxActive = true;
            gMapRxCh = h.ch;
            gMapRxExpect = h.total;
            gMapRxCount = 0;
        }
        if (!gMapRxActive || gMapRxCh != h.ch) {
            return;
        }
        const UsbMapPoint* pts =
            reinterpret_cast<const UsbMapPoint*>(p + sizeof(UsbMapChunkHdr));
        for (uint8_t i = 0; i < h.n && gMapRxCount < kMapLen; ++i) {
            if (h.start + i != static_cast<uint16_t>(gMapRxCount)) {
                // 欠番は詰めて受け取る（start を優先）
            }
            const int idx = static_cast<int>(h.start) + static_cast<int>(i);
            if (idx >= 0 && idx < kMapLen) {
                gMapRxX[idx] = pts[i].x;
                gMapRxY[idx] = pts[i].y;
                if (gMapRxCount < idx + 1) {
                    gMapRxCount = idx + 1;
                }
            }
        }
        gMapRxLastMs = millis();
        if (gMapRxExpect > 0 && gMapRxCount >= gMapRxExpect) {
            mapRxCommit();
        }
        return;
    }
}

static void usbRxReset() {
    gRxState = kUsbRxMagic0;
    gRxGot = 0;
}

static void pollUsbRx() {
    // マジック → type → len16 → payload → CRC。不一致なら 1 バイト捨てて再同期。
    while (Serial.available() > 0) {
        const int c = Serial.read();
        if (c < 0) {
            break;
        }
        const uint8_t b = static_cast<uint8_t>(c);
        switch (gRxState) {
        case kUsbRxMagic0:
            if (b == kUsbMagic0) {
                gRxState = kUsbRxMagic1;
            }
            break;
        case kUsbRxMagic1:
            gRxState = (b == kUsbMagic1) ? kUsbRxType : kUsbRxMagic0;
            if (gRxState == kUsbRxMagic0 && b == kUsbMagic0) {
                gRxState = kUsbRxMagic1;
            }
            break;
        case kUsbRxType:
            gRxType = b;
            gRxState = kUsbRxLen0;
            break;
        case kUsbRxLen0:
            gRxLen = b;
            gRxState = kUsbRxLen1;
            break;
        case kUsbRxLen1:
            gRxLen = static_cast<uint16_t>(gRxLen | (static_cast<uint16_t>(b) << 8));
            gRxGot = 0;
            if (gRxLen > kUsbMaxPayload) {
                usbRxReset();
            } else if (gRxLen == 0) {
                gRxState = kUsbRxCrc0;
            } else {
                gRxState = kUsbRxPayload;
            }
            break;
        case kUsbRxPayload:
            gRxPayload[gRxGot++] = b;
            if (gRxGot >= gRxLen) {
                gRxState = kUsbRxCrc0;
            }
            break;
        case kUsbRxCrc0:
            gRxCrcLo = b;
            gRxState = kUsbRxCrc1;
            break;
        case kUsbRxCrc1: {
            uint8_t tmp[3 + kUsbMaxPayload];
            tmp[0] = gRxType;
            tmp[1] = static_cast<uint8_t>(gRxLen & 0xFFu);
            tmp[2] = static_cast<uint8_t>(gRxLen >> 8);
            if (gRxLen > 0) {
                memcpy(tmp + 3, gRxPayload, gRxLen);
            }
            const uint16_t crc = usbCrc16(tmp, static_cast<size_t>(3) + gRxLen);
            const uint16_t got = static_cast<uint16_t>(gRxCrcLo) |
                                 (static_cast<uint16_t>(b) << 8);
            if (crc == got) {
                handleUsbFrame(gRxType, gRxPayload, gRxLen);
            }
            usbRxReset();
            break;
        }
        default:
            usbRxReset();
            break;
        }
    }
}

static bool wasButtonClicked() {
    static bool lastStable = false;
    static bool lastRaw = false;
    static uint32_t lastChangeMs = 0;

    const bool rawPressed = (digitalRead(kPinButton) == LOW);
    const uint32_t now = millis();
    if (rawPressed != lastRaw) {
        lastRaw = rawPressed;
        lastChangeMs = now;
        return false;
    }
    if ((now - lastChangeMs) < kButtonDebounceMs) {
        return false;
    }
    const bool clicked = lastStable && !rawPressed;
    lastStable = rawPressed;
    return clicked;
}

static void usbTask(void* /*arg*/) {
    Snapshot snap;
    uint32_t lastSeq = 0;
    bool haveLast = false;

    for (;;) {
        pollUsbRx();
        if (wasButtonClicked()) {
            gEvtBtn = 1;
            gIdentifyUntilMs = millis() + kIdentifyMs;
        }
        if (gMapRxActive && (millis() - gMapRxLastMs) > 5000) {
            mapRxFail(kUsbReasonBusy);
        }
        if (gHelloReq) {
            gHelloReq = 0;
            usbPrintHello();
        }
        if (gScanReady) {
            gScanReady = 0;
            usbDumpScan();
        }
        if (gProfDumpReq) {
            gProfDumpReq = 0;
            usbDumpProfile();
        }
        if (gProbeReady) {
            gProbeReady = 0;
            usbSend(kUsbProbe, &gProbeResult, sizeof(gProbeResult));
        }
        if (gCalMsgReady) {
            gCalMsgReady = 0;
            usbSend(gCalMsgType, gCalPayload, gCalPayloadLen);
        }
        if (gEvtOvercurrent) {
            gEvtOvercurrent = 0;
            UsbEvtOc ev{};
            ev.amp = gOverAmp;
            usbSend(kUsbEvtOc, &ev, sizeof(ev));
        }
        if (gEvtBtn) {
            gEvtBtn = 0;
            usbSend(kUsbEvtBtn, nullptr, 0);
        }
        const int dumpCh = gMapDumpCh;
        if (dumpCh >= 0) {
            gMapDumpCh = -1;
            usbDumpMap(dumpCh);
        } else if (copySnapshot(snap) && (!haveLast || snap.seq != lastSeq)) {
            lastSeq = snap.seq;
            haveLast = true;
            usbPrintFrame(snap);
        }
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

// ---------------------------------------------------------------------------
// リアルタイム制御（Core 1）
// ---------------------------------------------------------------------------
static void rtTask(void* /*arg*/) {
    TickType_t lastWake = xTaskGetTickCount();
    uint32_t prevStartUs = micros();
    bool first = true;
    uint32_t seq = 0;

    SensorFrame sense;
    RobotState state;
    Action action;
    Snapshot snap;

    for (;;) {
        const uint32_t t0 = micros();
        uint32_t t_period_us = kPeriodUs;
        if (!first) {
            t_period_us = t0 - prevStartUs;
        }
        prevStartUs = t0;
        first = false;
        ++seq;

        if (gScanReq) {
            gScanReq = 0;
            runI2cScan();
            gScanReady = 1;
        }
        if (gCalReq >= 0) {
            const int ch = gCalReq;
            gCalReq = -1;
            runCalibration(ch);
            // 校正後は周期計測をリセット
            first = true;
            lastWake = xTaskGetTickCount();
            continue;
        }
        if (gProbeReq == 1) {
            gProbeReq = 0;
            runProbeRoot(static_cast<uint8_t>(gProbeCh));
            gProbeReady = 1;
        } else if (gProbeReq == 2) {
            gProbeReq = 0;
            runProbeHub(gProbeHub, gProbeCh);
            gProbeReady = 1;
        }

        uint32_t mark = micros();
        readSensors(sense);
        const uint32_t t_sense = micros() - mark;

        mark = micros();
        buildState(sense, state);
        const uint32_t t_state = micros() - mark;

        mark = micros();
        selectAction(state, action);
        const uint32_t t_policy = micros() - mark;
        gLastAction = action;

        mark = micros();
        applyJoints(action);
        const uint32_t t_act = micros() - mark;

        const uint32_t t_loop = micros() - t0;

        fillSnapshot(snap, seq, t_period_us, t_sense, t_state, t_policy, t_act, t_loop,
                     sense, state, action);
        publishSnapshot(snap);

        const uint32_t nowMs = millis();
        if (nowMs < gIdentifyUntilMs) {
            const uint8_t hue = static_cast<uint8_t>((nowMs / 4) & 0xFF);
            gLeds[0] = CHSV(hue, 255, 160);
            FastLED.show();
        } else {
            bool anyAs = false;
            for (int i = 0; i < kJointCount; ++i) {
                if (sense.as5600_ok[i]) {
                    anyAs = true;
                }
            }
            if (snap.overrun || (gMode == WorkMode::Robot && !gServoOk)) {
                setLed(180, 0, 0);
            } else if (!anyAs) {
                setLed(((t0 / 250000) % 2) ? 80 : 0, 0, 0);
            } else if (gMode == WorkMode::Lab && gOutMask == 0) {
                setLed(20, 40, 90);
            } else {
                setLed(0, 90, 20);
            }
        }

        vTaskDelayUntil(&lastWake, pdMS_TO_TICKS(kPeriodMs));
    }
}

// ---------------------------------------------------------------------------
// 起動
// ---------------------------------------------------------------------------
static void findIna226() {
    for (int i = 0; i < kInaCount; ++i) {
        gInaPresent[i] = false;
        const JointRoute r = jointRoute(i);
        if (r.ina_addr == 0) {
            continue;
        }
        gIna226[i].setAddress(r.ina_addr);
        openMux(r.ina_hub, r.ina_ch);
        delay(5);
        if (gIna226[i].isConnected() && gIna226[i].begin()) {
            gInaPresent[i] = true;
        }
        closeMux(r.ina_hub);
    }
}

void setup() {
    Serial.begin(115200);
    delay(400);

    pinMode(kPinButton, INPUT_PULLUP);
    pinMode(kPinLed, OUTPUT);
    FastLED.addLeds<SK6812, kPinLed, GRB>(gLeds, kNumLeds);
    FastLED.setBrightness(kLedBrightness);
    FastLED.clear(true);

    for (int i = 0; i < kJointCount; ++i) {
        gUnwrapInited[i] = false;
        gLastAction.cmd_deg[i] = NAN;
        gManualCmd[i] = kHoldDeg;
    }

    loadProfile();

    {
        const JointRoute r0 = jointRoute(0);
        openMux(r0.act_hub, r0.act_ch);
        gServoOk = gServo.begin(&Wire, kPinSda, kPinScl, r0.act_addr);
        if (gServoOk) {
            Wire.setClock(100000);
            Wire.setTimeOut(20);
            for (int i = 0; i < kJointCount; ++i) {
                const JointRoute ri = jointRoute(i);
                openMux(ri.act_hub, ri.act_ch);
                gServo.setOnePinMode(ri.servo_ch, SERVO_CTL_MODE);
                closeMux(ri.act_hub);
            }
        }
        closeMux(r0.act_hub);
    }

    gAs5600.begin(kPinSda, kPinScl, 100000);
    Wire.setClock(100000);
    Wire.setTimeOut(20);

    findIna226();

    memset(gCal, 0, sizeof(gCal));
    for (int i = 0; i < kJointCount; ++i) {
        loadCalibration(i);
    }

    memset(&gSnapFront, 0, sizeof(gSnapFront));
    gMode = WorkMode::Lab;
    gOutMask = 0;
    gHelloReq = 1;

    xTaskCreatePinnedToCore(usbTask, "usb", kUsbStack, nullptr, 1, nullptr, kUsbCore);
    xTaskCreatePinnedToCore(rtTask, "rt", kRtStack, nullptr, 2, nullptr, kRtCore);
}

void loop() {
    vTaskDelay(pdMS_TO_TICKS(1000));
}
