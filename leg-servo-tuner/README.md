# leg-servo-tuner

**【注意】 このディレクトリ内のコードは現在更新されていません。上位互換の機能は [robotics-hub](../robotics-hub/) にあります。**

サーボの角度を 1 つずつ調整する Flask ウェブアプリです。バックエンドから **`robot-daemon`** の REST API（既定 `http://127.0.0.1:5000`）へプロキシする構成です。

## 起動方法

別ターミナルで **`robot-daemon`** を起動したうえで:

```bash
cd leg-servo-tuner
python app.py
```
