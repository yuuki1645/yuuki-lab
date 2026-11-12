/**
 * ATOM S3R の内蔵ディスプレイに "Hello World" だけを出す。
 *
 * 画面は 128x128。既定フォントを 2 倍にすると 1 文字 12px なので、
 * "Hello World"（11 文字）は 132px になり右端が切れる。だから 2 行に分ける。
 * ボード判定とバックライトは M5.begin に任せる。ここは文字を置くだけ。
 */

#include <M5Unified.h>

// 画面の中央。setup で実寸に取り直す。
static int gCenterX = 64;
static int gCenterY = 64;

static void drawHello() {
    // 黒で塗り、白文字。背景色も黒にして、文字の周りのゴミを残さない。
    M5.Display.fillScreen(TFT_BLACK);
    M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
    M5.Display.setTextSize(2);
    M5.Display.setTextDatum(middle_center);
    // 2 倍フォントの行間は 16px。上下に 10px ずらして中央に揃える。
    M5.Display.drawString("Hello", gCenterX, gCenterY - 10);
    M5.Display.drawString("World", gCenterX, gCenterY + 10);
}

void setup() {
    auto cfg = M5.config();
    M5.begin(cfg);

    gCenterX = M5.Display.width() / 2;
    gCenterY = M5.Display.height() / 2;
    drawHello();

    // 画面が真っ黒のとき、USB 側で起動したかを見るため。
    Serial.println("Hello World");
}

void loop() {
    // 表示は setup で完了している。空ループで CPU を回し続けない。
    delay(1000);
}
