/**
 * PORT.B の行テキスト。中身の角度だけを USB テレメトリへ渡す。
 * RS485 の待ちは ATOM 側。ここが 30 ms 止まると、CAN の 20 Hz が遅れる。
 */

#include "sms_link.hpp"

#include <Arduino.h>
#include <stdlib.h>
#include <string.h>

// core-test と同じ PORT.B。黄が送信、白が受信。ストレートケーブル。
static constexpr int kLinkTxPin = 9;
static constexpr int kLinkRxPin = 8;
static constexpr uint32_t kLinkBaud = 115200;

// ATOM は 200 ms 黙ると、出力中のトルクを切る。表示だけでも hb は残す。
static constexpr uint32_t kHeartbeatMs = 50;
static constexpr uint32_t kWatchRepeatMs = 1000;
// これを超えて行が来なければ、最後の角度を残さない。
static constexpr uint32_t kFreshMs = 250;

static constexpr int kSlotCount = 4;
static constexpr float kCountsPerRev = 4096.0f;
static constexpr int kZeroCount = 2048;

// UART1。USB CDC が Serial、CAN は TWAI なので UART は空いている。
static HardwareSerial gLink(1);

struct Slot {
    uint8_t id;
    bool ok;
    float cmd_deg;
    float pos_deg;
    float volt_v;
    float amp_a;
    uint32_t ms;
};

static Slot gSlot[kSlotCount];
static char gLine[160];
static size_t gLineLen = 0;
static bool gDiscard = false;
static uint32_t gNextHbMs = 0;
static uint32_t gNextWatchMs = 0;

static int slotIndex(uint8_t id) {
    if (id < 1 || id > kSlotCount) {
        return -1;
    }
    return static_cast<int>(id) - 1;
}

// ビット15が符号。試験の decode_bit15 と同じ。
static int decodeBit15(unsigned raw) {
    if (raw & 0x8000u) {
        return -static_cast<int>(raw & 0x7FFFu);
    }
    return static_cast<int>(raw & 0x7FFFu);
}

// 2048 を 0° にする。正方向は取り付け済みなので、ここでは符号を反転しない。
static float countsToDeg(unsigned raw) {
    const float counts = static_cast<float>(decodeBit15(raw) - kZeroCount);
    return counts * (360.0f / kCountsPerRev);
}

static bool tokenInt(const char* line, const char* key, long* out) {
    const char* p = strstr(line, key);
    if (p == nullptr) {
        return false;
    }
    p += strlen(key);
    if (*p != '=') {
        return false;
    }
    char* end = nullptr;
    const long v = strtol(p + 1, &end, 10);
    if (end == p + 1) {
        return false;
    }
    *out = v;
    return true;
}

static void sendLine(const char* line) {
    const size_t n = strlen(line);
    if (gLink.availableForWrite() < static_cast<int>(n)) {
        return;
    }
    gLink.write(reinterpret_cast<const uint8_t*>(line), n);
}

static void takeSm(const char* line) {
    long id = 0;
    long ok = 0;
    if (!tokenInt(line, "id", &id) || !tokenInt(line, "ok", &ok)) {
        return;
    }
    const int index = slotIndex(static_cast<uint8_t>(id));
    if (index < 0) {
        return;
    }
    Slot& slot = gSlot[index];
    slot.id = static_cast<uint8_t>(id);
    slot.ms = millis();
    slot.ok = ok == 1;
    if (!slot.ok) {
        return;
    }
    long goal = 0;
    long pos = 0;
    long volt = 0;
    long curr = 0;
    if (!tokenInt(line, "goal", &goal) || !tokenInt(line, "pos", &pos) || !tokenInt(line, "volt", &volt) ||
        !tokenInt(line, "curr", &curr)) {
        slot.ok = false;
        return;
    }
    // 指令も現在角も同じゼロ。goal を 2048 引きしないと、真下で約 180° になる。
    slot.cmd_deg = countsToDeg(static_cast<unsigned>(goal));
    slot.pos_deg = countsToDeg(static_cast<unsigned>(pos));
    // 試験画面の単位。volt は 0.1 V、curr は 6.5 mA。画面の電流は A。
    slot.volt_v = static_cast<float>(volt) / 10.0f;
    slot.amp_a = static_cast<float>(curr) * 6.5f / 1000.0f;
}

static void takeLine(char* line) {
    if (strncmp(line, "@sm ", 4) != 0) {
        return;
    }
    takeSm(line);
}

static void pollRx() {
    while (gLink.available() > 0) {
        const char c = static_cast<char>(gLink.read());
        if (c == '\r') {
            continue;
        }
        if (c == '\n') {
            if (gDiscard) {
                gDiscard = false;
                gLineLen = 0;
                continue;
            }
            gLine[gLineLen] = '\0';
            if (gLineLen > 0) {
                takeLine(gLine);
            }
            gLineLen = 0;
            continue;
        }
        if (gDiscard) {
            continue;
        }
        if (gLineLen >= sizeof(gLine) - 1) {
            gDiscard = true;
            gLineLen = 0;
            continue;
        }
        gLine[gLineLen++] = c;
    }
}

void smsLinkBegin() {
    for (int i = 0; i < kSlotCount; ++i) {
        gSlot[i].id = static_cast<uint8_t>(i + 1);
        gSlot[i].ok = false;
        gSlot[i].cmd_deg = 0.0f;
        gSlot[i].pos_deg = 0.0f;
        gSlot[i].volt_v = 0.0f;
        gSlot[i].amp_a = 0.0f;
        gSlot[i].ms = 0;
    }
    gLink.setRxBufferSize(1024);
    gLink.setTxBufferSize(256);
    gLink.begin(kLinkBaud, SERIAL_8N1, kLinkRxPin, kLinkTxPin);
    gNextHbMs = millis();
    gNextWatchMs = millis();
}

void smsLinkPoll() {
    pollRx();
    const uint32_t now = millis();
    // 起動が遅い ATOM にも届くよう、watch は 1 秒ごとに繰り返す。中身は同じ。
    if (static_cast<int32_t>(now - gNextWatchMs) >= 0) {
        gNextWatchMs = now + kWatchRepeatMs;
        sendLine("watch 1\n");
    }
    if (static_cast<int32_t>(now - gNextHbMs) >= 0) {
        gNextHbMs = now + kHeartbeatMs;
        sendLine("hb\n");
    }
}

bool smsLinkRead(uint8_t id, SmsSample* out) {
    const int index = slotIndex(id);
    if (index < 0 || out == nullptr) {
        return false;
    }
    const Slot& slot = gSlot[index];
    const uint32_t now = millis();
    out->fresh = slot.ms != 0 && (uint32_t)(now - slot.ms) <= kFreshMs;
    out->ok = out->fresh && slot.ok;
    out->cmd_deg = slot.cmd_deg;
    out->pos_deg = slot.pos_deg;
    out->volt_v = slot.volt_v;
    out->amp_a = slot.amp_a;
    return true;
}
