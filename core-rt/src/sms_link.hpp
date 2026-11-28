#pragma once

/**
 * 腰の PORT.B から、RS485 ベースを載せた ATOM S3R の行を読む。
 *
 * ATOM は atom-test の grove-rs485。`watch 1` で ID 1〜4 を 20 Hz で返す。
 *   1 右ひざピッチ、2 右かかとピッチ、3 左ひざピッチ、4 左かかとピッチ。
 * フィードバックは表示用。目標角は `smsLinkGoal` が来たときだけ書く。
 * 未指令のあいだはトルクを入れない。全停止は `smsLinkRelease` で脱力する。
 * 角度は試験画面と同じで、カウント 2048 を真下 0° とする。
 * カウントが増える向きは、ひざは後ろへ折れる正、右かかとはつま先が上がる正。
 * 左かかとピッチ（ID 4）だけ、0° を中心に符号を反転して同じ正に合わせる。
 * 関節角の正本は yuuki-lab の docs/joint_angles.md。
 */

#include <stdint.h>

struct SmsSample {
    /** 250 ms 以内に、その ID の行が来ている。 */
    bool fresh;
    /** fresh かつサーボが応答した。欠測の ID は fresh でも ok は false。 */
    bool ok;
    /** サーボが追っている目標角（度）。真下 0°。 */
    float cmd_deg;
    /** フィードバックの現在角（度）。画面の補正はこの値。 */
    float pos_deg;
    float volt_v;
    float amp_a;
    /** その行が来てから何ミリ秒か。一度も来ていなければ 65535。 */
    uint16_t age_ms;
};

/** UART1 を PORT.B（送信 GPIO9、受信 GPIO8）で開く。5V は呼び出し側が先に出す。 */
void smsLinkBegin();

/** 受信行を解釈し、hb と watch 1 を足す。制御周期から呼ぶ。ブロックしない。 */
void smsLinkPoll();

/**
 * ID 1〜4 の最新サンプル。未知の ID は false。
 * 行が 250 ms 途切れたら fresh は false（ATOM 抜け）。
 */
bool smsLinkRead(uint8_t id, SmsSample* out);

/**
 * ID 1〜4 の目標角を 1 本だけ積む。度は真下 0°。
 * 同じ角度の繰り返しは、ATOM 側へは変化したときだけ出る。
 */
void smsLinkGoal(uint8_t id, float deg);

/** 指令済みの SM105BL のトルクを切る。0° へは動かさない。 */
void smsLinkRelease();
