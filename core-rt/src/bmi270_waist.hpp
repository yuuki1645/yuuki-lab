#pragma once

/**
 * 腰の CoreS3 に載っている BMI270。
 *
 * M5.begin() は呼ばない。USB CDC と、すでに開いている AW9523 の Wire1 を壊すため。
 * Wire1（SDA GPIO12、SCL GPIO11）は Grove の 5V を出したあとで、ここが同じバスを使う。
 * アドレスは 0x69。チップ ID は 0x24。設定ファイルを書かないと計測は始まらない。
 *
 * 返す軸はチップの軸。体の前・左・上への入れ替えは bmi270_waist.cpp の表だけ。
 */

/** 設定ファイルを書き、加速度 ±4 g・角速度 ±2000 deg/s にする。失敗時は false。 */
bool bmi270Begin();

/**
 * 体座標の比力 [g] と角速度 [rad/s]。
 * 比力は、止まって上を向く軸が +1。方策の重力ベクトルはこれの逆向き。
 * 読めないときは false。100 ms 以内の直前値があればそれを返す。
 */
bool bmi270Read(float specific_force_g[3], float gyro_rad_s[3]);

/** 最後に読めたサンプルからのミリ秒。未取得は 65535。 */
uint16_t bmi270AgeMs();
