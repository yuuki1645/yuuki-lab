/**
 * ATOM S3R の底面 G5, G6, G7, G8 から、RDS51150 用の PWM を出す。
 *
 * サーボの角度はパルスのハイ時間で決まる。この個体の対応は次のとおり。
 *   0°   = 500 µs
 *   135° = 1500 µs（中点）
 *   270° = 2500 µs
 * フレームは 330 Hz（周期 約 3030 µs）。角度はハイ時間だけで決まる。
 * 270° の 2500 µs でも、1 周期の中に収まる。
 * オシロでは、この周期のハイ時間をそのまま読む。
 *
 * ESP32-S3 の LEDC は、この Arduino コアでは 14 ビットまで。
 * 3030 µs / 16384 ≒ 0.185 µs 刻み。GUI はファームが返した µs を表示する。
 *
 * 起動しただけではピンを駆動しない。入力＋内部プルダウンにして、
 * 信号が浮いてサーボが震えないようにする。USB の「出力 ON」以降だけ出す。
 * 正面ボタン（GPIO41、押すと LOW）でも、すぐ止める。
 *
 * Grove は G1/G2。ここは底面の G5〜G8。信号は 3.3 V。
 * サーボの電源は基板側。USB の 5 V では RDS51150 は動かない。GND は共通。
 *
 * PC からは 1 行 1 コマンド。数値に小数は使わない（printf の %f を避ける）。
 *   hello
 *   stat
 *   out 0|1
 *   en CH 0|1          CH は 0=G5, 1=G6, 2=G7, 3=G8
 *   deg CH TENTHS      TENTHS は 0.1° 単位。1350 が 135.0°
 */

#include <Arduino.h>
#include "soc/ledc_caps.h"

// 底面ヘッダ。Grove ではない。
static constexpr int kPins[4] = {5, 6, 7, 8};
// チャンネル 0 と 1 はタイマを共有する。4 本を別タイマにするため 0,2,4,6。
static constexpr int kLedcCh[4] = {0, 2, 4, 6};
static constexpr int kPinButton = 41;

static constexpr int kCount = 4;
static constexpr uint32_t kHz = 330;
static constexpr int kBits = 14;  // ESP32-S3 の LEDC 上限。16 だと ledcSetup が失敗する
static_assert(kBits <= SOC_LEDC_TIMER_BIT_WIDE_NUM, "LEDC resolution");
static constexpr uint32_t kDutyMax = (1u << kBits) - 1u;

static constexpr int kMinX10 = 0;
static constexpr int kMaxX10 = 2700;  // 270.0°
static constexpr int kCenterX10 = 1350;
static constexpr uint16_t kPulseMinUs = 500;
static constexpr uint16_t kPulseMaxUs = 2500;
// 最長パルスが 1 周期を超えると、ハイのまま次のフレームに食い込む。
static_assert(kPulseMaxUs * kHz < 1000000UL, "pulse longer than period");

static constexpr uint32_t kButtonMs = 30;

struct Channel {
    bool en;       // このピンを使う。出力 OFF のあいだは覚えておくだけ
    bool driving;  // 今 LEDC がピンを握っている
    int x10;       // 0.1° 単位
};

static Channel gCh[kCount];
static bool gOutput = false;
static bool gLedcOk = false;
static bool gMapOk = false;
static uint32_t gActualHz = 0;

// ボタンは離すまで一度だけ。チャタリングで何度も切らない。
// since==0 を「未計測」にすると、millis()==0 のあいだ押されていたとき区別できない。
static uint32_t gButtonSince = 0;
static bool gButtonTiming = false;
static bool gButtonLatched = false;

/** 0.1° → ハイ時間。0=500、1350=1500、2700=2500 になる割り算。 */
static uint16_t tenthsToPulse(int x10) {
    // +1350 は分母 2700 の半分。正の値だけを四捨五入する。
    const int us = kPulseMinUs + (x10 * (kPulseMaxUs - kPulseMinUs) + 1350) / 2700;
    return static_cast<uint16_t>(us);
}

/**
 * ハイ時間 → 14 ビットのデューティ。
 * 1000000/330 は 3030 で、端数 0.3 µs が落ちる。Hz から直接割る。
 * タイマが 330 ちょうどにならないときは、実際の周波数で幅を合わせる。
 */
static uint32_t pulseToDuty(uint16_t us) {
    if (gActualHz == 0) {
        return 0;
    }
    return static_cast<uint32_t>(
        (static_cast<uint64_t>(us) * gActualHz * kDutyMax + 500000ULL) / 1000000ULL);
}

static bool mapLooksRight() {
    return tenthsToPulse(0) == 500 && tenthsToPulse(kCenterX10) == 1500 &&
           tenthsToPulse(kMaxX10) == 2500;
}

static void printErr(const char* cmd, const char* msg) {
    Serial.print("@err cmd=");
    Serial.print(cmd);
    Serial.print(" msg=");
    Serial.println(msg);
}

static void printHello() {
    Serial.print("@hello name=atom-test-pwm hz=");
    Serial.print(gActualHz);
    Serial.print(" bits=");
    Serial.print(kBits);
    Serial.print(" pins=5,6,7,8 min_us=500 max_us=2500 center_x10=1350 map=");
    Serial.println(gMapOk ? 1 : 0);
}

static void printStat() {
    Serial.print("@stat out=");
    Serial.print(gOutput ? 1 : 0);
    Serial.print(" en=");
    for (int i = 0; i < kCount; ++i) {
        if (i) {
            Serial.print(',');
        }
        Serial.print(gCh[i].en ? 1 : 0);
    }
    Serial.print(" x10=");
    for (int i = 0; i < kCount; ++i) {
        if (i) {
            Serial.print(',');
        }
        Serial.print(gCh[i].x10);
    }
    Serial.print(" us=");
    for (int i = 0; i < kCount; ++i) {
        if (i) {
            Serial.print(',');
        }
        // 無効なピンは 0。オシロに何も出ていないことが分かる。
        Serial.print((gOutput && gCh[i].en) ? tenthsToPulse(gCh[i].x10) : 0);
    }
    Serial.print(" hz=");
    Serial.println(gActualHz);
}

/** パルスをやめる。LOW 固定にはしない。入力にしてフレームが続かないようにする。 */
static void releasePin(int index) {
    Channel& ch = gCh[index];
    if (ch.driving) {
        ledcDetachPin(kPins[index]);
        ch.driving = false;
    }
    // 内部プルダウンは、開放した信号が浮いてエッジに見えないようにするだけ。
    // 基板側にプルアップがあれば、そちらの方が勝つ。
    pinMode(kPins[index], INPUT_PULLDOWN);
}

/**
 * デューティを書いてからピンを繋ぐ。
 * 先に繋ぐと、デューティ 0 の 1 周期（パルスなし、または極短）がサーボに入る。
 */
static void drivePin(int index) {
    Channel& ch = gCh[index];
    const uint16_t us = tenthsToPulse(ch.x10);
    ledcWrite(kLedcCh[index], pulseToDuty(us));
    if (!ch.driving) {
        ledcAttachPin(kPins[index], kLedcCh[index]);
        ch.driving = true;
    }
}

static void refreshPin(int index) {
    if (gOutput && gCh[index].en) {
        drivePin(index);
    } else {
        releasePin(index);
    }
}

static void refreshAll() {
    for (int i = 0; i < kCount; ++i) {
        refreshPin(i);
    }
}

static bool channelOk(int index) {
    return index >= 0 && index < kCount;
}

static void cmdOut(int on) {
    if (on != 0 && on != 1) {
        printErr("out", "bad_arg");
        return;
    }
    if (on && (!gLedcOk || !gMapOk)) {
        printErr("out", gLedcOk ? "pulse_map" : "ledc");
        return;
    }
    gOutput = on == 1;
    refreshAll();
    Serial.print("@ok cmd=out value=");
    Serial.println(gOutput ? 1 : 0);
}

static void cmdEn(int index, int on) {
    if (!channelOk(index) || (on != 0 && on != 1)) {
        printErr("en", "bad_arg");
        return;
    }
    gCh[index].en = on == 1;
    refreshPin(index);
    Serial.print("@ok cmd=en ch=");
    Serial.print(index);
    Serial.print(" pin=");
    Serial.print(kPins[index]);
    Serial.print(" value=");
    Serial.println(on);
}

static void cmdDeg(int index, int x10) {
    if (!channelOk(index) || x10 < kMinX10 || x10 > kMaxX10) {
        printErr("deg", "bad_arg");
        return;
    }
    gCh[index].x10 = x10;
    // 出力中のピンだけ、今の周期の次から幅が変わる。止まっているピンは覚えるだけ。
    if (gOutput && gCh[index].en) {
        drivePin(index);
    }
    Serial.print("@ok cmd=deg ch=");
    Serial.print(index);
    Serial.print(" pin=");
    Serial.print(kPins[index]);
    Serial.print(" x10=");
    Serial.print(x10);
    Serial.print(" us=");
    Serial.print(tenthsToPulse(x10));
    Serial.print(" out=");
    Serial.print(gOutput ? 1 : 0);
    Serial.print(" en=");
    Serial.println(gCh[index].en ? 1 : 0);
}

static void handleLine(char* line) {
    int a = 0;
    int b = 0;
    if (strcmp(line, "hello") == 0) {
        printHello();
    } else if (strcmp(line, "stat") == 0) {
        printStat();
    } else if (sscanf(line, "out %d", &a) == 1) {
        cmdOut(a);
    } else if (sscanf(line, "en %d %d", &a, &b) == 2) {
        cmdEn(a, b);
    } else if (sscanf(line, "deg %d %d", &a, &b) == 2) {
        cmdDeg(a, b);
    } else {
        printErr("?", "bad_cmd");
    }
}

static void pollUsb() {
    static char line[64];
    static size_t len = 0;
    while (Serial.available() > 0) {
        const char c = static_cast<char>(Serial.read());
        if (c == '\r') {
            continue;
        }
        if (c == '\n') {
            line[len] = '\0';
            if (len > 0) {
                handleLine(line);
            }
            len = 0;
            continue;
        }
        if (len < sizeof(line) - 1) {
            line[len++] = c;
        }
    }
}

/** 正面ボタンでパルスを切る。GUI が固まっても、指で止められる。 */
static void pollButton() {
    const bool down = digitalRead(kPinButton) == LOW;
    const uint32_t now = millis();
    if (down) {
        if (!gButtonTiming) {
            gButtonTiming = true;
            gButtonSince = now;
        } else if (!gButtonLatched && (now - gButtonSince) >= kButtonMs && gOutput) {
            gButtonLatched = true;
            gOutput = false;
            refreshAll();
            Serial.println("@ok cmd=out value=0 src=button");
        }
    } else {
        gButtonTiming = false;
        gButtonLatched = false;
    }
}

static void setupLedc() {
    gLedcOk = true;
    uint32_t hz = 0;
    for (int i = 0; i < kCount; ++i) {
        const uint32_t got = ledcSetup(kLedcCh[i], kHz, kBits);
        if (got == 0) {
            gLedcOk = false;
        } else if (hz == 0) {
            hz = got;
        }
        gCh[i].en = true;
        gCh[i].driving = false;
        gCh[i].x10 = kCenterX10;
        releasePin(i);
    }
    gActualHz = hz;
}

void setup() {
    // ホストがいないときに flush すると、USB CDC がそこで止まる。flush しない。
    Serial.setTxBufferSize(1024);
    Serial.begin(115200);
    Serial.setTimeout(10);

    pinMode(kPinButton, INPUT_PULLUP);
    gMapOk = mapLooksRight();
    setupLedc();
    printHello();
}

void loop() {
    pollUsb();
    pollButton();
    // LEDC はハードウェアが回す。ここは USB とボタンだけでよい。
    delay(1);
}
