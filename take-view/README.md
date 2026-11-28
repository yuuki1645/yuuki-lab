# 閉じた実験の画面

腰の CoreS3 が残した take を、診断と異常マップで見る。読むだけで、ファイルは書き換えない。

常時起動するのはこのプロセスだけです。robotics-hub と `lab_debug.py` は、実機のそばで USB が見えたときだけ使います。

## 読み先

`LAB_EXPERIMENTS_ROOT` があればそれを使う。無ければ、ログイン中のユーザーの `~/.yuuki-lab/storage.yaml` の `archive_root` を使う。開いている断片はそこには無いので、この画面には出ません。

## 起動

```text
pip install -r take-view/requirements.txt
cd take-view/web
npm install
npm run build
cd ..
python serve.py
```

画面は `http://127.0.0.1:8780/lab` です。ポートは `TAKE_VIEW_PORT` で変えられます。

開発中に画面だけ差し替えるときは、別の端末で `python serve.py` を動かしたまま `npm run dev` を使う。画面は `http://127.0.0.1:5178/lab` で、API は 8780 へ渡します。
