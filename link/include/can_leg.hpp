#pragma once

/**
 * 腰 CoreS3 と片脚 ATOM S3R の CAN 契約。机上の can-ping とは別。
 *
 * 500 kbps、標準 11 bit ID。1 フレームは 8 バイト。
 * 右が leg 0、左が leg 1。不明な脚は指令を受けない。
 *
 * 腰 → 脚  ID = 0x100 + leg * 0x10 + slot
 * 脚 → 腰  ID = 0x180 + leg * 0x20 + slot
 * 不明な脚の生存通知だけ 0x1F0。
 *
 * 計測とサーボ指令は複数フレーム。各フレームの先頭が連番で、
 * 連番が揃った組だけを採用する。途中の組は捨てる。
 *
 * 角度の計測は 0.01 度の uint16（0〜36000）。0xFFFF は欠測。
 * サーボ指令は 0.1 度の int16。
 */

#include <stdint.h>
#include <string.h>

static constexpr uint32_t kCanLegBitrate = 500000;
static constexpr uint32_t kCanCmdBase = 0x100;
static constexpr uint32_t kCanCmdStride = 0x10;
static constexpr uint32_t kCanTelBase = 0x180;
static constexpr uint32_t kCanTelStride = 0x20;
static constexpr uint32_t kCanUnknownHello = 0x1F0;
static constexpr int kCanLegCount = 2;
static constexpr int kCanAxes = 5;
static constexpr uint32_t kCanStaleMs = 200;

static constexpr uint8_t kCanRoleUnknown = 0;
static constexpr uint8_t kCanRoleRight = 1;
static constexpr uint8_t kCanRoleLeft = 2;

static constexpr uint8_t kCanFlagOvercurrent = 0x01;
static constexpr uint8_t kCanFlagForceOff = 0x01;

enum CanCmdSlot : uint8_t {
    kCmdA = 0,
    kCmdB = 1,
    kCmdRoute = 2,
    kCmdScan = 3,
    kCmdIdentify = 4,
};

enum CanTelSlot : uint8_t {
    kTelHello = 0,
    kTelAngA = 1,
    kTelAngB = 2,
    kTelMag = 3,
    kTelAgc = 4,
    kTelVoltA = 5,
    kTelVoltB = 6,
    kTelAmpA = 7,
    kTelAmpB = 8,
    kTelFootA = 9,
    kTelFootB = 10,
    kTelScanHead = 11,
    kTelScanNode = 12,
};

static constexpr uint16_t kCanSampleBits = 0x03FF;  // slot 1..10
static constexpr uint16_t kCanCentiInvalid = 0xFFFF;

static inline uint32_t canCmdId(int leg, uint8_t slot) {
    return kCanCmdBase + static_cast<uint32_t>(leg) * kCanCmdStride + slot;
}

static inline uint32_t canTelId(int leg, uint8_t slot) {
    return kCanTelBase + static_cast<uint32_t>(leg) * kCanTelStride + slot;
}

static inline bool canParseTel(uint32_t id, int& leg, uint8_t& slot) {
    if (id == kCanUnknownHello) {
        leg = -1;
        slot = kTelHello;
        return true;
    }
    if (id < kCanTelBase) {
        return false;
    }
    const uint32_t off = id - kCanTelBase;
    if (off >= static_cast<uint32_t>(kCanLegCount) * kCanTelStride) {
        return false;
    }
    leg = static_cast<int>(off / kCanTelStride);
    slot = static_cast<uint8_t>(off % kCanTelStride);
    return true;
}

static inline bool canParseCmd(uint32_t id, int& leg, uint8_t& slot) {
    if (id < kCanCmdBase) {
        return false;
    }
    const uint32_t off = id - kCanCmdBase;
    if (off >= static_cast<uint32_t>(kCanLegCount) * kCanCmdStride) {
        return false;
    }
    leg = static_cast<int>(off / kCanCmdStride);
    slot = static_cast<uint8_t>(off % kCanCmdStride);
    return true;
}

static inline void canPutU16(uint8_t* p, uint16_t v) {
    p[0] = static_cast<uint8_t>(v & 0xFF);
    p[1] = static_cast<uint8_t>(v >> 8);
}

static inline uint16_t canGetU16(const uint8_t* p) {
    return static_cast<uint16_t>(p[0] | (static_cast<uint16_t>(p[1]) << 8));
}

static inline void canPutI16(uint8_t* p, int16_t v) {
    canPutU16(p, static_cast<uint16_t>(v));
}

static inline int16_t canGetI16(const uint8_t* p) {
    return static_cast<int16_t>(canGetU16(p));
}

static inline void canPutU32(uint8_t* p, uint32_t v) {
    p[0] = static_cast<uint8_t>(v & 0xFF);
    p[1] = static_cast<uint8_t>((v >> 8) & 0xFF);
    p[2] = static_cast<uint8_t>((v >> 16) & 0xFF);
    p[3] = static_cast<uint8_t>((v >> 24) & 0xFF);
}

static inline uint32_t canGetU32(const uint8_t* p) {
    return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
}

/** 片脚 5 軸分の、1 周期の計測。got のビットが slot 1..10 に対応する。 */
struct CanLegSample {
    uint8_t seq;
    uint8_t as_ok;
    uint8_t ina_ok;
    uint8_t mag[kCanAxes];
    uint8_t agc[kCanAxes];
    uint16_t centi[kCanAxes];
    int16_t bus_mv[kCanAxes];
    int16_t ma[kCanAxes];
    uint8_t foot_ok;
    uint8_t foot_mask;
    uint32_t foot_seq;
    uint16_t foot_mv[4];
    uint16_t got;
};

struct CanLegHello {
    uint8_t seq;
    uint8_t role;
    uint8_t hubs;
    uint8_t servo_ok;
    uint8_t flags;
    uint16_t i2c_err;
    uint8_t sense_ms;
};

struct CanLegCommand {
    uint8_t seq;
    uint8_t mask;
    uint8_t flags;
    int16_t deci[kCanAxes];
    uint8_t got;
};

static inline void canSampleBegin(CanLegSample& s, uint8_t seq) {
    memset(&s, 0, sizeof(s));
    s.seq = seq;
    for (int i = 0; i < kCanAxes; ++i) {
        s.centi[i] = kCanCentiInvalid;
        s.mag[i] = 255;
        s.agc[i] = 255;
    }
}

/** 計測フレームを足す。組が揃ったら true。連番が変わると途中の組は捨てる。 */
static inline bool canSamplePush(CanLegSample& s, uint8_t slot, const uint8_t* d) {
    if (slot < kTelAngA || slot > kTelFootB) {
        return false;
    }
    if (s.got == 0 || d[0] != s.seq) {
        canSampleBegin(s, d[0]);
    }
    switch (slot) {
        case kTelAngA:
            s.as_ok = d[1];
            s.centi[0] = canGetU16(d + 2);
            s.centi[1] = canGetU16(d + 4);
            s.centi[2] = canGetU16(d + 6);
            break;
        case kTelAngB:
            s.as_ok = d[1];
            s.centi[3] = canGetU16(d + 2);
            s.centi[4] = canGetU16(d + 4);
            break;
        case kTelMag:
            memcpy(s.mag, d + 1, kCanAxes);
            break;
        case kTelAgc:
            memcpy(s.agc, d + 1, kCanAxes);
            break;
        case kTelVoltA:
            s.ina_ok = d[1];
            s.bus_mv[0] = canGetI16(d + 2);
            s.bus_mv[1] = canGetI16(d + 4);
            s.bus_mv[2] = canGetI16(d + 6);
            break;
        case kTelVoltB:
            s.ina_ok = d[1];
            s.bus_mv[3] = canGetI16(d + 2);
            s.bus_mv[4] = canGetI16(d + 4);
            break;
        case kTelAmpA:
            s.ma[0] = canGetI16(d + 1);
            s.ma[1] = canGetI16(d + 3);
            s.ma[2] = canGetI16(d + 5);
            break;
        case kTelAmpB:
            s.ma[3] = canGetI16(d + 1);
            s.ma[4] = canGetI16(d + 3);
            break;
        case kTelFootA:
            s.foot_ok = d[1];
            s.foot_mask = d[2];
            s.foot_mv[0] = canGetU16(d + 3);
            s.foot_mv[1] = canGetU16(d + 5);
            // mv2 の上位バイトは FootB が先に届いていても残す。
            s.foot_mv[2] = static_cast<uint16_t>((s.foot_mv[2] & 0xFF00) | d[7]);
            break;
        case kTelFootB:
            s.foot_mv[2] = static_cast<uint16_t>((s.foot_mv[2] & 0x00FF) |
                                                 (static_cast<uint16_t>(d[1]) << 8));
            s.foot_mv[3] = canGetU16(d + 2);
            s.foot_seq = canGetU32(d + 4);
            break;
        default:
            return false;
    }
    s.got = static_cast<uint16_t>(s.got | (1u << (slot - 1)));
    return s.got == kCanSampleBits;
}

static inline void canPackHello(uint8_t* d, const CanLegHello& h) {
    memset(d, 0, 8);
    d[0] = h.seq;
    d[1] = h.role;
    d[2] = h.hubs;
    d[3] = h.servo_ok;
    d[4] = h.flags;
    canPutU16(d + 5, h.i2c_err);
    d[7] = h.sense_ms;
}

static inline void canUnpackHello(CanLegHello& h, const uint8_t* d) {
    h.seq = d[0];
    h.role = d[1];
    h.hubs = d[2];
    h.servo_ok = d[3];
    h.flags = d[4];
    h.i2c_err = canGetU16(d + 5);
    h.sense_ms = d[7];
}

static inline void canPackSample(uint8_t frame[10][8], const CanLegSample& s) {
    memset(frame, 0, 10 * 8);
    frame[0][0] = s.seq;
    frame[0][1] = s.as_ok;
    canPutU16(frame[0] + 2, s.centi[0]);
    canPutU16(frame[0] + 4, s.centi[1]);
    canPutU16(frame[0] + 6, s.centi[2]);

    frame[1][0] = s.seq;
    frame[1][1] = s.as_ok;
    canPutU16(frame[1] + 2, s.centi[3]);
    canPutU16(frame[1] + 4, s.centi[4]);

    frame[2][0] = s.seq;
    memcpy(frame[2] + 1, s.mag, kCanAxes);

    frame[3][0] = s.seq;
    memcpy(frame[3] + 1, s.agc, kCanAxes);

    frame[4][0] = s.seq;
    frame[4][1] = s.ina_ok;
    canPutI16(frame[4] + 2, s.bus_mv[0]);
    canPutI16(frame[4] + 4, s.bus_mv[1]);
    canPutI16(frame[4] + 6, s.bus_mv[2]);

    frame[5][0] = s.seq;
    frame[5][1] = s.ina_ok;
    canPutI16(frame[5] + 2, s.bus_mv[3]);
    canPutI16(frame[5] + 4, s.bus_mv[4]);

    frame[6][0] = s.seq;
    canPutI16(frame[6] + 1, s.ma[0]);
    canPutI16(frame[6] + 3, s.ma[1]);
    canPutI16(frame[6] + 5, s.ma[2]);

    frame[7][0] = s.seq;
    canPutI16(frame[7] + 1, s.ma[3]);
    canPutI16(frame[7] + 3, s.ma[4]);

    frame[8][0] = s.seq;
    frame[8][1] = s.foot_ok;
    frame[8][2] = s.foot_mask;
    canPutU16(frame[8] + 3, s.foot_mv[0]);
    canPutU16(frame[8] + 5, s.foot_mv[1]);
    frame[8][7] = static_cast<uint8_t>(s.foot_mv[2] & 0xFF);

    frame[9][0] = s.seq;
    frame[9][1] = static_cast<uint8_t>(s.foot_mv[2] >> 8);
    canPutU16(frame[9] + 2, s.foot_mv[3]);
    canPutU32(frame[9] + 4, s.foot_seq);
}

static inline bool canCommandPush(CanLegCommand& c, uint8_t slot, const uint8_t* d) {
    if (slot != kCmdA && slot != kCmdB) {
        return false;
    }
    if (c.got == 0 || d[0] != c.seq) {
        memset(&c, 0, sizeof(c));
        c.seq = d[0];
    }
    if (slot == kCmdA) {
        c.mask = d[1];
        c.deci[0] = canGetI16(d + 2);
        c.deci[1] = canGetI16(d + 4);
        c.deci[2] = canGetI16(d + 6);
        c.got = static_cast<uint8_t>(c.got | 0x01);
    } else {
        c.flags = d[1];
        c.deci[3] = canGetI16(d + 2);
        c.deci[4] = canGetI16(d + 4);
        c.got = static_cast<uint8_t>(c.got | 0x02);
    }
    return c.got == 0x03;
}

static inline void canPackCommand(uint8_t a[8], uint8_t b[8], uint8_t seq, uint8_t mask,
                                  uint8_t flags, const int16_t deci[kCanAxes]) {
    memset(a, 0, 8);
    memset(b, 0, 8);
    a[0] = seq;
    a[1] = mask;
    canPutI16(a + 2, deci[0]);
    canPutI16(a + 4, deci[1]);
    canPutI16(a + 6, deci[2]);
    b[0] = seq;
    b[1] = flags;
    canPutI16(b + 2, deci[3]);
    canPutI16(b + 4, deci[4]);
}
