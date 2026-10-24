/**
 * CoreS3 側の CAN。ドライバは制御タスクだけが触る。
 * 受信キューは 1 周期分の計測が溢えない長さにしてある。
 */

#include "can_host.hpp"

#include <Arduino.h>
#include <math.h>
#include <string.h>

#include "can_leg.hpp"
#include "driver/twai.h"

struct LegLive {
    bool seen;
    uint32_t seenMs;
    uint32_t lastMs;
    uint32_t sampleMs;
    bool haveSample;
    bool overSeen;
    CanLegHello hello;
    CanLegSample committed;
    CanLegSample partial;
    bool scanHead;
    uint8_t scanSeq;
    uint8_t scanCount;
    uint8_t scanGot;
    UsbScanNode scanNode[24];
};

static LegLive gLeg[kCanLegCount];
static uint8_t gCmdSeq = 1;
static uint8_t gScanSeq = 1;
static bool gReady = false;

static bool canSend(uint32_t id, const uint8_t* data) {
    canHostPoll();
    if (!gReady) {
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

static void recover() {
    if (!gReady) {
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

bool canHostStart(int txPin, int rxPin) {
    twai_general_config_t general = TWAI_GENERAL_CONFIG_DEFAULT(
        static_cast<gpio_num_t>(txPin), static_cast<gpio_num_t>(rxPin), TWAI_MODE_NORMAL);
    // 片脚が 1 周期に 11 枚出す。5 枚の既定キューでは途中で落ちる。
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
    gReady = true;
    return true;
}

static void noteScan(int leg, uint8_t slot, const uint8_t* d) {
    if (leg < 0 || leg >= kCanLegCount || d[0] != gScanSeq) {
        return;
    }
    LegLive& live = gLeg[leg];
    if (slot == kTelScanHead) {
        live.scanHead = true;
        live.scanSeq = d[0];
        live.scanCount = d[1] < 24 ? d[1] : 24;
        live.scanGot = 0;
        return;
    }
    if (slot != kTelScanNode || !live.scanHead || live.scanSeq != d[0]) {
        return;
    }
    const uint8_t index = d[1];
    if (index >= live.scanCount || index >= 24) {
        return;
    }
    UsbScanNode node{};
    node.hub = d[2];
    node.ch = static_cast<int8_t>(d[3]);
    node.addr = d[4];
    node.kind = d[5];
    node.mag = d[6];
    node.agc = d[7];
    const bool fresh = live.scanNode[index].addr == 0 && live.scanNode[index].kind == 0;
    live.scanNode[index] = node;
    if (fresh) {
        ++live.scanGot;
    }
}

static bool scanDone(const LegLive& live) {
    return live.scanHead && live.scanSeq == gScanSeq && live.scanGot >= live.scanCount;
}

void canHostPoll() {
    recover();
    if (!gReady) {
        return;
    }
    twai_message_t msg{};
    while (twai_receive(&msg, 0) == ESP_OK) {
        if (msg.data_length_code < 8) {
            continue;
        }
        int leg = -1;
        uint8_t slot = 0;
        if (!canParseTel(msg.identifier, leg, slot)) {
            continue;
        }
        if (leg < 0) {
            continue;
        }
        LegLive& live = gLeg[leg];
        if (!live.seen) {
            live.seenMs = millis();
        }
        live.seen = true;
        live.lastMs = millis();
        if (slot == kTelHello) {
            canUnpackHello(live.hello, msg.data);
            continue;
        }
        if (slot == kTelScanHead || slot == kTelScanNode) {
            noteScan(leg, slot, msg.data);
            continue;
        }
        if (canSamplePush(live.partial, slot, msg.data)) {
            live.committed = live.partial;
            live.haveSample = true;
            live.sampleMs = millis();
            live.partial.got = 0;
        }
    }
}

static bool legStale(const LegLive& live, uint32_t now) {
    if (!live.seen) {
        return false;
    }
    // 生存も計測も 200 ms 途切れたら、その脚は落ちたものとする。
    // 最初の組が揃うまでの短いあいだは、まだ落ちた扱いにしない。
    if (static_cast<uint32_t>(now - live.lastMs) > kCanStaleMs) {
        return true;
    }
    if (!live.haveSample) {
        return static_cast<uint32_t>(now - live.seenMs) > kCanStaleMs;
    }
    return static_cast<uint32_t>(now - live.sampleMs) > kCanStaleMs;
}

static void fillLeg(CanHostView& out, int leg) {
    const int base = leg * kCanAxes;
    const CanLegSample& s = gLeg[leg].committed;
    for (int i = 0; i < kCanAxes; ++i) {
        CanHostAxis& axis = out.axis[base + i];
        axis.mag = s.mag[i];
        axis.agc = s.agc[i];
        axis.as_ok = 0;
        axis.ina_ok = 0;
        axis.raw_deg = NAN;
        axis.volt = NAN;
        axis.amp = NAN;
        axis.watt = NAN;
        if ((s.as_ok & (1u << i)) != 0 && s.centi[i] != kCanCentiInvalid) {
            axis.as_ok = 1;
            axis.raw_deg = static_cast<float>(s.centi[i]) / 100.0f;
        }
        if ((s.ina_ok & (1u << i)) != 0) {
            axis.ina_ok = 1;
            axis.volt = static_cast<float>(s.bus_mv[i]) / 1000.0f;
            axis.amp = static_cast<float>(s.ma[i]) / 1000.0f;
            axis.watt = axis.volt * axis.amp;
        }
    }
    CanHostFoot& foot = out.foot[leg];
    foot.ok = s.foot_ok;
    foot.mask = s.foot_mask;
    foot.seq = s.foot_seq;
    memcpy(foot.mv, s.foot_mv, sizeof(foot.mv));
}

static void blankLeg(CanHostView& out, int leg) {
    const int base = leg * kCanAxes;
    for (int i = 0; i < kCanAxes; ++i) {
        CanHostAxis& axis = out.axis[base + i];
        axis.as_ok = 0;
        axis.ina_ok = 0;
        axis.mag = 255;
        axis.agc = 255;
        axis.raw_deg = NAN;
        axis.volt = NAN;
        axis.amp = NAN;
        axis.watt = NAN;
    }
    memset(&out.foot[leg], 0, sizeof(out.foot[leg]));
}

void canHostRead(CanHostView& out) {
    memset(&out, 0, sizeof(out));
    for (int i = 0; i < kCanHostJoints; ++i) {
        out.axis[i].raw_deg = NAN;
        out.axis[i].volt = NAN;
        out.axis[i].amp = NAN;
        out.axis[i].watt = NAN;
        out.axis[i].mag = 255;
        out.axis[i].agc = 255;
    }
    const uint32_t now = millis();
    uint32_t err = 0;
    bool any = false;
    bool servos = true;
    for (int leg = 0; leg < kCanLegCount; ++leg) {
        LegLive& live = gLeg[leg];
        if (!live.seen) {
            blankLeg(out, leg);
            continue;
        }
        any = true;
        err += live.hello.i2c_err;
        const bool stale = legStale(live, now);
        if (stale || !live.haveSample) {
            if (stale) {
                out.fault = true;
            }
            servos = false;
            blankLeg(out, leg);
        } else {
            fillLeg(out, leg);
            out.sense_us += static_cast<uint32_t>(live.hello.sense_ms) * 1000u;
            if (live.hello.servo_ok == 0) {
                servos = false;
            }
        }
        const bool over = (live.hello.flags & kCanFlagOvercurrent) != 0;
        if (over && !live.overSeen) {
            out.overcurrent = true;
            out.over_amp = 0.0f;
            if (live.haveSample) {
                for (int i = 0; i < kCanAxes; ++i) {
                    if ((live.committed.ina_ok & (1u << i)) == 0) {
                        continue;
                    }
                    const float amp = fabsf(static_cast<float>(live.committed.ma[i]) / 1000.0f);
                    if (amp > out.over_amp) {
                        out.over_amp = amp;
                    }
                }
            }
        }
        live.overSeen = over;
    }
    if (!any) {
        servos = false;
    }
    out.servo_ok = servos ? 1 : 0;
    out.i2c_err = err > 0xFFFF ? 0xFFFF : static_cast<uint16_t>(err);
}

void canHostSendMotion(const float* deg, uint16_t mask, bool forceOff) {
    int16_t deci[kCanAxes];
    uint8_t a[8];
    uint8_t b[8];
    const uint8_t seq = gCmdSeq++;
    if (gCmdSeq == 0) {
        gCmdSeq = 1;
    }
    for (int leg = 0; leg < kCanLegCount; ++leg) {
        if (!gLeg[leg].seen) {
            continue;
        }
        const int base = leg * kCanAxes;
        uint8_t local = static_cast<uint8_t>((mask >> base) & 0x1F);
        uint8_t flags = 0;
        if (forceOff) {
            local = 0;
            flags = kCanFlagForceOff;
        }
        for (int i = 0; i < kCanAxes; ++i) {
            deci[i] = static_cast<int16_t>(deg[base + i] * 10.0f);
        }
        canPackCommand(a, b, seq, local, flags, deci);
        canSend(canCmdId(leg, kCmdA), a);
        canSend(canCmdId(leg, kCmdB), b);
    }
}

static void sendRouteFrame(int leg, const uint8_t* data) {
    canSend(canCmdId(leg, kCmdRoute), data);
}

void canHostSendRoutes(const JointRoute* routes, const FootRoute* feet, uint16_t jointEn,
                       uint8_t footEn, uint8_t gen) {
    if (gen == 0) {
        gen = 1;
    }
    for (int leg = 0; leg < kCanLegCount; ++leg) {
        if (!gLeg[leg].seen) {
            continue;
        }
        uint8_t d[8];
        memset(d, 0, sizeof(d));
        d[0] = gen;
        d[1] = 0xFE;
        d[2] = static_cast<uint8_t>((jointEn >> (leg * kCanAxes)) & 0x1F);
        d[3] = static_cast<uint8_t>((footEn >> leg) & 0x01);
        sendRouteFrame(leg, d);

        for (int i = 0; i < kCanAxes; ++i) {
            uint8_t raw[sizeof(JointRoute)];
            memcpy(raw, &routes[leg * kCanAxes + i], sizeof(JointRoute));
            memset(d, 0, sizeof(d));
            d[0] = gen;
            d[1] = static_cast<uint8_t>(i);
            memcpy(d + 2, raw, 6);
            sendRouteFrame(leg, d);
            memset(d, 0, sizeof(d));
            d[0] = gen;
            d[1] = static_cast<uint8_t>(0x80 | i);
            memcpy(d + 2, raw + 6, 4);
            sendRouteFrame(leg, d);
        }
        memset(d, 0, sizeof(d));
        d[0] = gen;
        d[1] = 0x05;
        d[2] = feet[leg].hub;
        d[3] = static_cast<uint8_t>(feet[leg].ch);
        d[4] = feet[leg].addr;
        sendRouteFrame(leg, d);
    }
}

int canHostCollectScan(UsbScanNode* out, int maxNodes, uint32_t waitMs) {
    gScanSeq = static_cast<uint8_t>(gScanSeq + 1);
    if (gScanSeq == 0) {
        gScanSeq = 1;
    }
    for (int leg = 0; leg < kCanLegCount; ++leg) {
        gLeg[leg].scanHead = false;
        gLeg[leg].scanGot = 0;
        gLeg[leg].scanCount = 0;
        memset(gLeg[leg].scanNode, 0, sizeof(gLeg[leg].scanNode));
    }
    uint8_t req[8] = {};
    req[0] = gScanSeq;
    req[1] = 1;
    for (int leg = 0; leg < kCanLegCount; ++leg) {
        canSend(canCmdId(leg, kCmdScan), req);
    }
    const uint32_t deadline = millis() + waitMs;
    while (static_cast<int32_t>(deadline - millis()) > 0) {
        canHostPoll();
        int seen = 0;
        bool all = true;
        for (int leg = 0; leg < kCanLegCount; ++leg) {
            if (!gLeg[leg].seen) {
                continue;
            }
            ++seen;
            if (!scanDone(gLeg[leg])) {
                all = false;
            }
        }
        if (seen > 0 && all) {
            break;
        }
        delay(2);
    }
    int n = 0;
    for (int leg = 0; leg < kCanLegCount && n < maxNodes; ++leg) {
        if (!scanDone(gLeg[leg])) {
            continue;
        }
        for (uint8_t i = 0; i < gLeg[leg].scanCount && n < maxNodes; ++i) {
            out[n++] = gLeg[leg].scanNode[i];
        }
    }
    return n;
}

void canHostIdentify() {
    uint8_t d[8] = {};
    d[0] = 1;
    for (int leg = 0; leg < kCanLegCount; ++leg) {
        canSend(canCmdId(leg, kCmdIdentify), d);
    }
}
