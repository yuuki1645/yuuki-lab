/**
 * 片脚の Grove 直下 8Servos を、一度だけ 0x26 にする確認用ファーム。
 *
 * pio run -e servo-addr -t upload
 * pio device monitor -e servo-addr
 *
 * 起動のたびにアドレスを読み、表示するだけ。w を送ったときだけ書く。
 * PaHub をすべて閉じた状態で 0x25 だけが見えるとき、その 1 台が直下である。
 * すね側はチャンネルの向こうにいるので、この書き込みは届かない。
 * アドレスは 8Servos 自身のフラッシュに残る。USB を抜き差ししたあとの
 * 起動表示で、直下 0x26・すね 0x25 が残っているかを見る。
 *
 * Grove は G2=SDA、G1=SCL。本線の can-leg と同じピン。
 * 右すねの 8Servos は PaHub 0x72 のチャンネル 0。
 * 左すねの 8Servos は PaHub 0x73 のチャンネル 5。
 */

#include <Arduino.h>
#include <Wire.h>

#include "pahub.hpp"

static constexpr int kSdaPin = 2;
static constexpr int kSclPin = 1;
static constexpr uint32_t kI2cHz = 100000;
static constexpr uint32_t kI2cTimeoutMs = 20;
static constexpr uint32_t kHubProbeTimeoutMs = 5;
static constexpr uint32_t kReportMs = 2000;
// 直下に残すアドレス。すね側は工場出荷の 0x25 のままにする。
static constexpr uint8_t kRootAddr = 0x26;
static constexpr uint8_t kShinAddr = 0x25;
static constexpr uint8_t kAddrReg = 0xFF;

static constexpr uint8_t kHubRightThigh = 0x70;
static constexpr uint8_t kHubLeftThigh = 0x71;
static constexpr uint8_t kHubRightShin = 0x72;
static constexpr uint8_t kHubLeftShin = 0x73;
static constexpr uint8_t kHubList[] = {kHubRightThigh, kHubLeftThigh, kHubRightShin, kHubLeftShin};

static constexpr uint8_t kRoleUnknown = 0;
static constexpr uint8_t kRoleRight = 1;
static constexpr uint8_t kRoleLeft = 2;

struct Probe {
    bool at25;
    bool at26;
};

static uint8_t gHubMask = 0;
static uint8_t gRole = kRoleUnknown;

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
        gRole = kRoleRight;
    } else if (left && !right) {
        gRole = kRoleLeft;
    } else {
        gRole = kRoleUnknown;
    }
}

static Probe probeServos() {
    Probe out{};
    out.at25 = i2cPing(kShinAddr);
    out.at26 = i2cPing(kRootAddr);
    return out;
}

static const char* yn(bool on) {
    return on ? "yes" : "no";
}

static const char* roleName() {
    if (gRole == kRoleRight) {
        return "right";
    }
    if (gRole == kRoleLeft) {
        return "left";
    }
    return "unknown";
}

/** 役割が決まっているときだけ、すねの 8Servos チャンネルを開く。 */
static bool openShin() {
    closeHubs();
    uint8_t hub = 0;
    int8_t ch = -1;
    if (gRole == kRoleRight) {
        hub = kHubRightShin;
        ch = 0;
    } else if (gRole == kRoleLeft) {
        hub = kHubLeftShin;
        ch = 5;
    } else {
        return false;
    }
    if ((gHubMask & (1u << (hub - 0x70))) == 0) {
        return false;
    }
    PaHub h(hub);
    if (!h.select(ch)) {
        closeHubs();
        return false;
    }
    delay(2);
    return true;
}

static void printVerdict(const Probe& closed, bool shinOpened, const Probe& shin) {
    if (closed.at25 && closed.at26) {
        Serial.println("result: チャンネルを閉じても 0x25 と 0x26 の両方が応答する。書き込まない。");
        return;
    }
    if (!closed.at25 && !closed.at26) {
        Serial.println("result: 直下に 8Servos が無い。Grove の電源と配線を確認する。");
        return;
    }
    if (closed.at25 && !closed.at26) {
        Serial.println("result: 直下はまだ 0x25。w を送ると 0x26 に書く。");
        return;
    }
    if (!shinOpened) {
        Serial.println("result: 直下は 0x26。すねは役割が不明なので未確認。");
        return;
    }
    if (shin.at26 && shin.at25) {
        Serial.println("result: 維持されている。直下は 0x26、すねは 0x25。");
        return;
    }
    if (shin.at26 && !shin.at25) {
        Serial.println("result: すねを開いても 0x25 が無い。すね側も 0x26 になったか、未接続。");
        return;
    }
    Serial.println("result: すねを開いた応答が想定と違う。表示の yes/no を見る。");
}

static void report() {
    detectRole();
    closeHubs();
    const Probe closed = probeServos();
    bool shinOpened = false;
    Probe shin{};
    if (openShin()) {
        shinOpened = true;
        shin = probeServos();
        closeHubs();
    }
    Serial.printf("servo-addr hubs=0x%02X role=%s\n", gHubMask, roleName());
    Serial.printf("closed: 0x25=%s 0x26=%s\n", yn(closed.at25), yn(closed.at26));
    if (gRole == kRoleUnknown) {
        Serial.println("shin: skip");
    } else if (!shinOpened) {
        Serial.println("shin: hub が無い");
    } else {
        const uint8_t hub = gRole == kRoleRight ? kHubRightShin : kHubLeftShin;
        const int ch = gRole == kRoleRight ? 0 : 5;
        Serial.printf("shin 0x%02X ch%d: 0x25=%s 0x26=%s\n", hub, ch, yn(shin.at25), yn(shin.at26));
    }
    printVerdict(closed, shinOpened, shin);
    Serial.println("---");
}

/**
 * 閉じたバスに 0x25 だけがあるとき、その 1 台の 0xFF へ 0x26 を書く。
 * チャンネルが開いているとすね側にも届くので、書く前に必ず閉じ直す。
 */
static void tryWrite() {
    detectRole();
    closeHubs();
    const Probe closed = probeServos();
    if (!(closed.at25 && !closed.at26)) {
        Serial.println("write: 中止。閉じたバスが 0x25 のみのときだけ書く。");
        return;
    }
    Wire.beginTransmission(kShinAddr);
    Wire.write(kAddrReg);
    Wire.write(kRootAddr);
    const uint8_t err = Wire.endTransmission();
    // 基板はフラッシュへ書いてから I2C を新しいアドレスでやり直す。
    delay(300);
    closeHubs();
    const Probe after = probeServos();
    Serial.printf("write: endTransmission=%u closed 0x25=%s 0x26=%s\n", err, yn(after.at25),
                  yn(after.at26));
    if (after.at26 && !after.at25) {
        Serial.println("write: 直下は 0x26 になった。USB を抜き差しして、起動表示が残るか確認する。");
    } else {
        Serial.println("write: 書き込み後の応答が想定と違う。抜き差しせず、上の行を見る。");
    }
}

void setup() {
    Serial.begin(115200);
    Serial.setTxBufferSize(1024);
    delay(200);
    Wire.begin(kSdaPin, kSclPin, kI2cHz);
    Wire.setTimeOut(kI2cTimeoutMs);
    Serial.println("servo-addr: 読み取りのみ。直下を 0x26 にするときは w");
    report();
}

void loop() {
    while (Serial.available() > 0) {
        const char c = static_cast<char>(Serial.read());
        if (c == 'w' || c == 'W') {
            tryWrite();
            report();
        }
    }
    static uint32_t next = 0;
    const uint32_t now = millis();
    if (static_cast<int32_t>(now - next) >= 0) {
        report();
        next = now + kReportMs;
    }
    delay(20);
}
