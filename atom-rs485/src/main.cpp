/**
 * ATOM S3R + ATOMIC RS485 ベースから、SM105BL を 1 台だけ試験する。
 *
 * USB（PC の GUI）と RS485（サーボ）のあいだを中継する。角度の計算はしない。
 * 起動時はトルクを入れない。arm は、現在位置を目標に書いてから保持させる。
 * 目標レジスタの初期値が 0 なので、先にトルクだけ入れると 0 カウントへ回る。
 *
 * PC からは 1 行 1 コマンド。応答も 1 行。
 *   hello / ping / info / id N / stream HZ
 *   apply LIMIT SPEED ACC / arm LIMIT SPEED ACC / damp LIMIT
 *   move COUNTS / torque 0
 * 20Hz の監視は stream 20。フィードバックはアドレス 40 から 31 バイト。
 */

#include <Arduino.h>

#include "sms_bus.hpp"

static uint8_t gStreamHz = 0;
static uint32_t gNextStreamMs = 0;
// arm または damp が成功したあとのみ move を通す。切断コマンドで戻す。
static bool gOutputOn = false;

static void printErr(const char* cmd, const char* msg) {
    Serial.print("@err cmd=");
    Serial.print(cmd);
    Serial.print(" msg=");
    Serial.print(msg);
    Serial.print(" tx=");
    Serial.println(smsLastTxHex());
}

static void printHello() {
    // self=0 はパケット組み立ての自己検査に落ちたとき。サーボにはまだ何も書いていない。
    Serial.printf("@hello name=atom-rs485 rx=%d tx=%d baud=%lu id=%u self=%d\n",
                  kRs485RxPin,
                  kRs485TxPin,
                  static_cast<unsigned long>(kRs485Baud),
                  smsId(),
                  smsSelfOk() ? 1 : 0);
}

static uint16_t u16le(const uint8_t* p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static bool rangeOk(int value, int lo, int hi) {
    return value >= lo && value <= hi;
}

static void printFbFail() {
    Serial.printf("@fb ms=%lu id=%u ok=0 err=timeout\n",
                  static_cast<unsigned long>(millis()),
                  smsId());
}

static void printFb(const SmsReply& reply) {
    const uint8_t* d = reply.data;
    Serial.printf(
        "@fb ms=%lu id=%u ok=1 st=%u torque=%u acc=%u cmd_pos=%u pwm=%u run_spd=%u limit=%u lock=%u "
        "r0=%u r1=%u r2=%u r3=%u r4=%u pos=%u spd=%u load=%u volt=%u temp=%u async=%u status=%u "
        "moving=%u goal=%u curr=%u\n",
        static_cast<unsigned long>(millis()),
        smsId(),
        reply.status,
        d[0],
        d[1],
        u16le(d + 2),
        u16le(d + 4),
        u16le(d + 6),
        u16le(d + 8),
        d[15],
        d[10],
        d[11],
        d[12],
        d[13],
        d[14],
        u16le(d + 16),
        u16le(d + 18),
        u16le(d + 20),
        d[22],
        d[23],
        d[24],
        d[25],
        d[26],
        u16le(d + 27),
        u16le(d + 29));
}

static void pollFeedback() {
    if (gStreamHz == 0) {
        return;
    }
    const uint32_t now = millis();
    if (static_cast<int32_t>(now - gNextStreamMs) < 0) {
        return;
    }
    gNextStreamMs = now + (1000u / gStreamHz);
    SmsReply reply;
    if (!smsRead(kRegBlock, kRegBlockLen, &reply)) {
        printFbFail();
        return;
    }
    printFb(reply);
}

static void cmdPing() {
    SmsReply reply;
    if (!smsPing(&reply)) {
        printErr("ping", "timeout");
        return;
    }
    Serial.printf("@ok cmd=ping id=%u st=%u\n", smsId(), reply.status);
}

static void cmdInfo() {
    SmsReply mem;
    SmsReply factory;
    if (!smsRead(0, 40, &mem)) {
        printErr("info", "timeout");
        return;
    }
    const bool fact = smsRead(80, 7, &factory);
    const uint8_t* d = mem.data;
    static const uint32_t kBauds[] = {1000000, 500000, 250000, 128000, 115200, 76800, 57600, 38400};
    const uint32_t bps = d[6] <= 7 ? kBauds[d[6]] : 0;
    // 1 本の printf にすると引数の取り違えが起きやすいので、意味ごとに分ける。
    Serial.print("@info ok=1");
    Serial.printf(" fact=%d fw_maj=%u fw_min=%u endian=%u srv_maj=%u srv_min=%u",
                  fact ? 1 : 0,
                  d[0],
                  d[1],
                  d[2],
                  d[3],
                  d[4]);
    Serial.printf(" id=%u baud=%u baud_bps=%lu delay=%u level=%u",
                  d[5],
                  d[6],
                  static_cast<unsigned long>(bps),
                  d[7],
                  d[8]);
    Serial.printf(" amin=%u amax=%u tmax=%u vmax=%u vmin=%u max_trq=%u",
                  u16le(d + 9),
                  u16le(d + 11),
                  d[13],
                  d[14],
                  d[15],
                  u16le(d + 16));
    Serial.printf(" phase=%u unload=%u led=%u kp=%u kd=%u ki=%u",
                  d[18],
                  d[19],
                  d[20],
                  d[21],
                  d[22],
                  d[23]);
    Serial.printf(" start_trq=%u ilimit=%u db_cw=%u db_ccw=%u prot_i=%u res=%u ofs=%u",
                  d[24],
                  d[25],
                  d[26],
                  d[27],
                  u16le(d + 28),
                  d[30],
                  u16le(d + 31));
    Serial.printf(" mode=%u hold=%u ptime=%u oload=%u spd_p=%u oc_time=%u spd_i=%u",
                  d[33],
                  d[34],
                  d[35],
                  d[36],
                  d[37],
                  d[38],
                  d[39]);
    if (fact) {
        const uint8_t* f = factory.data;
        Serial.printf(" thr=%u dts=%u spd_k=%u hts=%u spd_max=%u acc_max=%u acc_mul=%u",
                      f[0],
                      f[1],
                      f[2],
                      f[3],
                      f[4],
                      f[5],
                      f[6]);
    }
    Serial.println();
}

// 速度 0 は位相のビット3次第で「最高速」になる。試験コマンドでは拒否する。
static bool motionArgsOk(const char* cmd, int limit, int speed, int acc) {
    if (!rangeOk(limit, 0, 1000) || !rangeOk(speed, 1, 32767) || !rangeOk(acc, 0, 254)) {
        printErr(cmd, "bad_arg");
        return false;
    }
    return true;
}

static bool stageMotion(const char* cmd, int limit, int speed, int acc) {
    SmsReply reply;
    if (!smsWrite16(kRegTorqueLimit, (uint16_t)limit, &reply)) {
        printErr(cmd, "write_limit");
        return false;
    }
    if (!smsWrite8(kRegAcc, (uint8_t)acc, &reply)) {
        printErr(cmd, "write_acc");
        return false;
    }
    if (!smsWrite16(kRegSpeed, (uint16_t)speed, &reply)) {
        printErr(cmd, "write_speed");
        return false;
    }
    return true;
}

static void cmdApply(int limit, int speed, int acc) {
    if (!motionArgsOk("apply", limit, speed, acc)) {
        return;
    }
    if (!stageMotion("apply", limit, speed, acc)) {
        return;
    }
    Serial.printf("@ok cmd=apply limit=%d speed=%d acc=%d\n", limit, speed, acc);
}

static void cmdArm(int limit, int speed, int acc) {
    if (!motionArgsOk("arm", limit, speed, acc)) {
        return;
    }
    // 速度と制限を先に書く。目標位置の書き込みがトルクを自分でオンにする。
    if (!stageMotion("arm", limit, speed, acc)) {
        return;
    }
    SmsReply pos;
    if (!smsRead(kRegPresent, 2, &pos)) {
        printErr("arm", "read_pos");
        return;
    }
    const uint16_t raw = u16le(pos.data);
    SmsReply wrote;
    if (!smsWrite16(kRegGoal, raw, &wrote)) {
        // 書き込みが届いたか不明。出力が残らないよう、切る方は一度試みる。
        SmsReply off;
        smsWrite8(kRegTorque, kTorqueOff, &off);
        gOutputOn = false;
        printErr("arm", "write_goal");
        return;
    }
    gOutputOn = true;
    Serial.printf("@ok cmd=arm value=1 pos=%u st=%u\n", raw, wrote.status);
}

static void cmdDamp(int limit) {
    if (!rangeOk(limit, 0, 1000)) {
        printErr("damp", "bad_arg");
        return;
    }
    SmsReply reply;
    if (!smsWrite16(kRegTorqueLimit, (uint16_t)limit, &reply)) {
        printErr("damp", "write_limit");
        return;
    }
    if (!smsWrite8(kRegTorque, kTorqueDamp, &reply)) {
        printErr("damp", "timeout");
        return;
    }
    gOutputOn = true;
    Serial.printf("@ok cmd=damp value=1 st=%u\n", reply.status);
}

static void cmdTorqueOff() {
    SmsReply reply;
    if (!smsWrite8(kRegTorque, kTorqueOff, &reply)) {
        printErr("torque", "timeout");
        return;
    }
    gOutputOn = false;
    Serial.printf("@ok cmd=torque value=0 st=%u\n", reply.status);
}

static void cmdMove(int counts) {
    if (!gOutputOn) {
        printErr("move", "torque_off");
        return;
    }
    if (!rangeOk(counts, -32767, 32767)) {
        printErr("move", "bad_arg");
        return;
    }
    SmsReply reply;
    const uint16_t raw = smsEncodeSigned15(counts);
    if (!smsWrite16(kRegGoal, raw, &reply)) {
        printErr("move", "timeout");
        return;
    }
    Serial.printf("@ok cmd=move pos=%d raw=%u st=%u\n", counts, raw, reply.status);
}

static void handleLine(char* line) {
    int a = 0;
    int b = 0;
    int c = 0;
    if (strcmp(line, "hello") == 0) {
        printHello();
    } else if (strcmp(line, "ping") == 0) {
        cmdPing();
    } else if (strcmp(line, "info") == 0) {
        cmdInfo();
    } else if (strcmp(line, "torque 0") == 0 || strcmp(line, "torque0") == 0) {
        cmdTorqueOff();
    } else if (sscanf(line, "id %d", &a) == 1) {
        if (!rangeOk(a, 0, 253)) {
            printErr("id", "bad_arg");
            return;
        }
        smsSetId((uint8_t)a);
        // 宛先が変わったら、前の個体の「出力中」を引きずらない。
        gOutputOn = false;
        Serial.printf("@ok cmd=id value=%d\n", a);
    } else if (sscanf(line, "stream %d", &a) == 1) {
        if (!rangeOk(a, 0, 50)) {
            printErr("stream", "bad_arg");
            return;
        }
        gStreamHz = (uint8_t)a;
        gNextStreamMs = millis();
        Serial.printf("@ok cmd=stream value=%d\n", a);
    } else if (sscanf(line, "apply %d %d %d", &a, &b, &c) == 3) {
        cmdApply(a, b, c);
    } else if (sscanf(line, "arm %d %d %d", &a, &b, &c) == 3) {
        cmdArm(a, b, c);
    } else if (sscanf(line, "damp %d", &a) == 1) {
        cmdDamp(a);
    } else if (sscanf(line, "move %d", &a) == 1) {
        cmdMove(a);
    } else if (strncmp(line, "torque", 6) == 0) {
        // 1 は arm の仕事。128 は中点校正で、軸のゼロがずれる。
        printErr("torque", "use_arm_or_off");
    } else {
        printErr("?", "bad_cmd");
    }
}

static void pollUsb() {
    static char line[96];
    static size_t len = 0;
    while (Serial.available() > 0) {
        const char c = (char)Serial.read();
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

void setup() {
    // ホストがいないときに flush すると、USB CDC がそこで止まる。flush しない。
    Serial.setTxBufferSize(4096);
    Serial.begin(115200);
    Serial.setTimeout(10);
    smsBegin();
    printHello();
}

void loop() {
    pollUsb();
    pollFeedback();
}
