# leg-servo-tuner-react

**【注意】 このディレクトリ内のコードは現在更新されていません。上位互換の機能は [robotics-hub](../robotics-hub/) にあります。**

サーボの角度を 1 つずつ調整する React アプリです。

`leg-servo-tuner` を React で実装し直したものでした。

## 起動方法

【注意】 **`robot-daemon`**（既定ポート **5000**）が起動している前提で、フロントからサーボ API に接続します。

```bash
cd leg-servo-tuner-react
npm install
npx vite --host 0.0.0.0 --port 5173
```
