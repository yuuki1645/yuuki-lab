# motion-editor-react

React で作成されたモーションエディタです。**日常的な開発の中心は [robotics-hub](../robotics-hub/)** に移っています。

## 起動方法

【注意】 **`robot-daemon`** の API を叩くので、起動前に **robot-daemon**（リポジトリ直下の `robot-daemon/`，既定ポート **5000**）を起動してください。

```bash
cd motion-editor-react
npm install
npx vite --host 0.0.0.0 --port 5173
```
