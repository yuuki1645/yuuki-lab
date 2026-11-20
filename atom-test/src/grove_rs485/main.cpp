/**
 * ATOM S3R + ATOMIC RS485 ベース。CoreS3 からの Grove UART で SM105BL を 1 台動かす。
 *
 * 電源は Grove の 5V（CoreS3 の PORT.B）。USB は書き込みのときだけ挿し、その間は Grove を外す。
 * 動かすときに USB と Grove の 5V を同時につなぐと、二つの 5V がぶつかる。
 * サーボの 12V はこの 5V とは別で、ピン 2 だけに入れる。
 *
 * ストレートの Grove ケーブル（黄-黄、白-白、赤-赤、黒-黒）:
 *   黄 GPIO2 = 受信。CoreS3 PORT.B の黄 GPIO9（送信）から来る
 *   白 GPIO1 = 送信。CoreS3 PORT.B の白 GPIO8（受信）へ出す
 * RS485 は底面のまま。受信 GPIO5、送信 GPIO6。DE はベースが持つ。
 *
 * 指令は Grove だけが受ける。USB へは同じ行を出すが、挿していなくても待たない。
 * 角度の計算はしない。起動時はトルクを入れない。
 * arm は現在位置を目標に書いてから保持させる。目標の初期値は 0 なので、
 * 先にトルクだけ入れると 0 カウントへ回る。
 *
 * 1 行 1 コマンド。応答も 1 行。
 *   hello / ping / info / id N / stream HZ / hb
 *   apply LIMIT SPEED ACC / arm LIMIT SPEED ACC / damp LIMIT
 *   move COUNTS / torque 0
 * hb は CoreS3 が 50 ms ごとに足す生存確認で、返事は出さない。
 * 行が 200 ms 来なければ、出力中ならトルクを切る。
 * 20 Hz の監視は stream 20。フィードバックはアドレス 40 から 31 バイト。
 */

#include <Arduino.h>

#include <cstdarg>
#include <cstdio>
#include <cstring>

#include "sms_bus.hpp"

// UART1。UART2 は RS485、USB CDC は Serial。
static HardwareSerial gLink(1);

// 公式ピンマップ。黄が GPIO2、白が GPIO1。ストレートケーブルで CoreS3 の送信と対になる。
static constexpr int kLinkRxPin = 2;
static constexpr int kLinkTxPin = 1;
static constexpr uint32_t kLinkBaud = 115200;

// 機体の CAN と同じ。この間に行が来なければ脱力する。
static constexpr uint32_t kHostTimeoutMs = 200;
// Grove の送信待ち。これを超えたら行を切って、サーボ側の処理へ戻る。
static constexpr uint32_t kLinkSendBudgetMs = 40;

static uint8_t gStreamHz = 0;
static uint32_t gNextStreamMs = 0;
static uint32_t gLastHostMs = 0;
static uint32_t gNextOffMs = 0;
// arm または damp が成功したあとのみ move を通す。切断コマンドで戻す。
static bool gOutputOn = false;

// Grove が本線。USB はモニタ用で、ホストがいないときは捨てる。
static void emitRaw(const char* text, size_t n) {
    const uint32_t start = millis();
    size_t sent = 0;
    while (sent < n && (uint32_t)(millis() - start) < kLinkSendBudgetMs) {
        const size_t room = gLink.availableForWrite();
        if (room == 0) {
            delayMicroseconds(200);
            continue;
        }
        size_t chunk = n - sent;
        if (chunk > room) {
            chunk = room;
        }
        gLink.write(reinterpret_cast<const uint8_t*>(text) + sent, chunk);
        sent += chunk;
    }
    if (Serial) {
        Serial.write(reinterpret_cast<const uint8_t*>(text), n);
    }
}

static void emit(const char* text) {
    emitRaw(text, strlen(text));
}

static void emitf(const char* fmt, ...) {
    char buf[512];
    va_list args;
    va_start(args, fmt);
    const int wrote = vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    if (wrote <= 0) {
        return;
    }
    size_t n = static_cast<size_t>(wrote);
    if (n >= sizeof(buf)) {
        n = sizeof(buf) - 1;
    }
    emitRaw(buf, n);
}

static void printErr(const char* cmd, const char* msg) {
    emitf("@err cmd=%s msg=%s tx=%s\n", cmd, msg, smsLastTxHex());
}

static void printHello() {
    // self=0 はパケット組み立ての自己検査に落ちたとき。サーボにはまだ何も書いていない。
    emitf("@hello name=grove-rs485 link_rx=%d link_tx=%d rs485_rx=%d rs485_tx=%d baud=%lu id=%u self=%d\n",
          kLinkRxPin,
          kLinkTxPin,
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
    emitf("@fb ms=%lu id=%u ok=0 err=timeout\n", static_cast<unsigned long>(millis()), smsId());
}

static void printFb(const SmsReply& reply) {
    const uint8_t* d = reply.data;
    emitf("@fb ms=%lu id=%u ok=1 st=%u torque=%u acc=%u cmd_pos=%u pwm=%u run_spd=%u limit=%u lock=%u "
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
    emitf("@ok cmd=ping id=%u st=%u\n", smsId(), reply.status);
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
    emit("@info ok=1");
    emitf(" fact=%d fw_maj=%u fw_min=%u endian=%u srv_maj=%u srv_min=%u",
          fact ? 1 : 0,
          d[0],
          d[1],
          d[2],
          d[3],
          d[4]);
    emitf(" id=%u baud=%u baud_bps=%lu delay=%u level=%u",
          d[5],
          d[6],
          static_cast<unsigned long>(bps),
          d[7],
          d[8]);
    emitf(" amin=%u amax=%u tmax=%u vmax=%u vmin=%u max_trq=%u",
          u16le(d + 9),
          u16le(d + 11),
          d[13],
          d[14],
          d[15],
          u16le(d + 16));
    emitf(" phase=%u unload=%u led=%u kp=%u kd=%u ki=%u", d[18], d[19], d[20], d[21], d[22], d[23]);
    emitf(" start_trq=%u ilimit=%u db_cw=%u db_ccw=%u prot_i=%u res=%u ofs=%u",
          d[24],
          d[25],
          d[26],
          d[27],
          u16le(d + 28),
          d[30],
          u16le(d + 31));
    emitf(" mode=%u hold=%u ptime=%u oload=%u spd_p=%u oc_time=%u spd_i=%u",
          d[33],
          d[34],
          d[35],
          d[36],
          d[37],
          d[38],
          d[39]);
    if (fact) {
        const uint8_t* f = factory.data;
        emitf(" thr=%u dts=%u spd_k=%u hts=%u spd_max=%u acc_max=%u acc_mul=%u",
              f[0],
              f[1],
              f[2],
              f[3],
              f[4],
              f[5],
              f[6]);
    }
    emit("\n");
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
    emitf("@ok cmd=apply limit=%d speed=%d acc=%d\n", limit, speed, acc);
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
    emitf("@ok cmd=arm value=1 pos=%u st=%u\n", raw, wrote.status);
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
    emitf("@ok cmd=damp value=1 st=%u\n", reply.status);
}

// reason は cmd（行コマンド）か timeout（Grove が途切れた）。
static void cmdTorqueOff(const char* reason) {
    SmsReply reply;
    if (!smsWrite8(kRegTorque, kTorqueOff, &reply)) {
        printErr("torque", "timeout");
        return;
    }
    gOutputOn = false;
    emitf("@ok cmd=torque value=0 reason=%s st=%u\n", reason, reply.status);
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
    emitf("@ok cmd=move pos=%d raw=%u st=%u\n", counts, raw, reply.status);
}

static void handleLine(char* line) {
    int a = 0;
    int b = 0;
    int c = 0;
    // 生存確認。返事を出すと USB 側が 20 Hz で埋まる。
    if (strcmp(line, "hb") == 0) {
        return;
    }
    if (strcmp(line, "hello") == 0) {
        printHello();
    } else if (strcmp(line, "ping") == 0) {
        cmdPing();
    } else if (strcmp(line, "info") == 0) {
        cmdInfo();
    } else if (strcmp(line, "torque 0") == 0 || strcmp(line, "torque0") == 0) {
        cmdTorqueOff("cmd");
    } else if (sscanf(line, "id %d", &a) == 1) {
        if (!rangeOk(a, 0, 253)) {
            printErr("id", "bad_arg");
            return;
        }
        smsSetId((uint8_t)a);
        // 宛先が変わったら、前の個体の「出力中」を引きずらない。
        gOutputOn = false;
        emitf("@ok cmd=id value=%d\n", a);
    } else if (sscanf(line, "stream %d", &a) == 1) {
        if (!rangeOk(a, 0, 50)) {
            printErr("stream", "bad_arg");
            return;
        }
        gStreamHz = (uint8_t)a;
        gNextStreamMs = millis();
        emitf("@ok cmd=stream value=%d\n", a);
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

// 指令口は Grove だけ。USB から文字が来ても読まない。
static void pollLink() {
    static char line[96];
    static size_t len = 0;
    static bool discard = false;
    while (gLink.available() > 0) {
        const char c = (char)gLink.read();
        if (c == '\r') {
            continue;
        }
        if (c == '\n') {
            if (discard) {
                // 溢れた行は、途中までを指令として実行しない。
                discard = false;
                len = 0;
                continue;
            }
            line[len] = '\0';
            if (len > 0) {
                gLastHostMs = millis();
                handleLine(line);
            }
            len = 0;
            continue;
        }
        if (discard) {
            continue;
        }
        if (len >= sizeof(line) - 1) {
            discard = true;
            len = 0;
            emit("@err cmd=? msg=long\n");
            continue;
        }
        line[len++] = c;
    }
}

static void pollHostTimeout() {
    if (!gOutputOn) {
        return;
    }
    const uint32_t now = millis();
    if ((uint32_t)(now - gLastHostMs) < kHostTimeoutMs) {
        return;
    }
    // 失敗した切断を、毎ループの RS485 タイムアウトで埋め尽くさない。
    if (static_cast<int32_t>(now - gNextOffMs) < 0) {
        return;
    }
    gNextOffMs = now + 50;
    cmdTorqueOff("timeout");
}

void setup() {
    // ホストがいない。begin より前にバッファを広げ、送信待ちは 0 にして捨てる。
    Serial.setTxBufferSize(1024);
    Serial.begin(115200);
    Serial.setTxTimeoutMs(0);

    gLink.setRxBufferSize(1024);
    gLink.setTxBufferSize(1024);
    gLink.begin(kLinkBaud, SERIAL_8N1, kLinkRxPin, kLinkTxPin);

    smsBegin();
    gLastHostMs = millis();
    printHello();
}

void loop() {
    pollLink();
    pollHostTimeout();
    pollFeedback();
}
