#pragma once

/**
 * 腰の PORT.B から、RS485 ベースを載せた ATOM S3R の行を読む。
 *
 * ATOM は atom-test の grove-rs485。`watch 1` で ID 1〜4 を 20 Hz で返す。
 *   1 右ひざピッチ、2 右かかとピッチ、3 左ひざピッチ、4 左かかとピッチ。
 * この側はトルクも目標位置も書かない。表示のためのフィードバックだけ。
 * 角度は試験画面と同じで、カウント 2048 を真下 0° とする。
 * カウントが増える向きは、左右ともひざは後ろへ折れる正、かかとはつま先が上がる正。
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
