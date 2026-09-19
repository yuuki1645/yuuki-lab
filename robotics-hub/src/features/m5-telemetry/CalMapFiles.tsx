/**
 * 校正マップの JSON 保存・読込。
 * lab_debug.py の「JSON に保存」「JSON を開いて送信」と同じ as5600-servo-map-v1。
 */
import { useRef, type ChangeEvent } from "react";
import { downloadCalMap, parseCalMap } from "./calMapIo";
import type { M5Cal, M5Cmd } from "./types";

type Props = {
  cal: M5Cal | null;
  /** 送信先の論理関節。ファイルの channel よりこちらを優先（Python GUI と同じ） */
  ch: number;
  canCmd: boolean;
  send: (cmd: M5Cmd) => void;
};

export function CalMapFiles({ cal, ch, canCmd, send }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const points = cal?.map_points ?? [];
  const canSave = points.length >= 2;

  const onSave = () => {
    if (!canSave) {
      window.alert("先にボードからマップを取得するか、校正を完了してください。");
      return;
    }
    // 保存する channel は受信したマップの軸（Python save_map と同じ）
    downloadCalMap(cal?.map_ch ?? ch, points);
  };

  const onPick = () => {
    if (!canCmd) return;
    inputRef.current?.click();
  };

  const onFile = async (ev: ChangeEvent<HTMLInputElement>) => {
    const file = ev.target.files?.[0];
    ev.target.value = "";
    if (!file) return;
    try {
      const text = await file.text();
      const { channel: fileCh, points: pts } = parseCalMap(text);
      send({ op: "map_put", ch, points: pts, file_ch: fileCh });
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "マップを読めませんでした");
    }
  };

  return (
    <>
      <button type="button" className="m5__btn" disabled={!canSave} onClick={onSave}>
        JSON に保存
      </button>
      <button type="button" className="m5__btn" disabled={!canCmd} onClick={onPick}>
        JSON を開いて送信
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        hidden
        onChange={onFile}
      />
    </>
  );
}
