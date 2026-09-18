import { useCallback, useEffect, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";
import { getM5TelemetrySocketUrl } from "@/shared/constants";
import { M5_EVENTS_MAX, type M5Cal, type M5Cmd, type M5Control, type M5EventAppend, type M5EventSnapshot, type M5Frame, type M5Hello, type M5HistoryPoint, type M5Nvs, type M5Profile, type M5RecordStatus, type M5Scan, type M5Status } from "./types";
import { frameToHistory } from "./types";

export type M5WsStatus = "disconnected" | "connecting" | "connected";

const HISTORY_MAX = 160;

function applyHello(
  hello: M5Hello,
  setStatus: (v: M5Status | null) => void,
  setControl: (v: M5Control | null) => void,
  setFrame: (v: M5Frame | null) => void,
  setScan: (v: M5Scan | null) => void,
  setProfile: (v: M5Profile | null) => void,
  applyEventSnapshot: (snap: M5EventSnapshot | string[]) => void,
  setCal: (v: M5Cal | null) => void,
  setNvs: (v: M5Nvs | null) => void,
  historyRef: { current: M5HistoryPoint[] },
  setHistory: (v: M5HistoryPoint[]) => void
): void {
  if (hello.status) setStatus(hello.status);
  if (hello.control) setControl(hello.control);
  if (hello.frame) {
    setFrame(hello.frame);
    const pt = frameToHistory(hello.frame);
    historyRef.current = [pt];
    setHistory([pt]);
  } else if (hello.frame === null) {
    setFrame(null);
  }
  if (hello.scan) setScan(hello.scan);
  if (hello.profile) setProfile(hello.profile);
  if (hello.events) applyEventSnapshot(hello.events);
  if (hello.cal) setCal(hello.cal);
  if (hello.nvs) setNvs(hello.nvs);
}

function applyHelloRecord(
  hello: M5Hello,
  setRecordStatus: (v: M5RecordStatus | null) => void
): void {
  if (hello.record) setRecordStatus(hello.record);
}

export type M5TelemetryStream = {
  wsStatus: M5WsStatus;
  url: string;
  status: M5Status | null;
  control: M5Control | null;
  frame: M5Frame | null;
  scan: M5Scan | null;
  profile: M5Profile | null;
  events: string[];
  eventHeadSeq: number;
  eventTailSeq: number;
  cal: M5Cal | null;
  nvs: M5Nvs | null;
  recordStatus: M5RecordStatus | null;
  history: M5HistoryPoint[];
  lastError: string | null;
  send: (cmd: M5Cmd) => void;
  reconnect: () => void;
};

/**
 * Windows PC 上の lab_debug.py が立てる Socket.IO（既定 :8794）を購読する。
 * iPad が接続すると PC GUI は表示専用になる。
 */
export function useM5TelemetryStream(active: boolean): M5TelemetryStream {
  const [wsStatus, setWsStatus] = useState<M5WsStatus>("disconnected");
  const [status, setStatus] = useState<M5Status | null>(null);
  const [control, setControl] = useState<M5Control | null>(null);
  const [frame, setFrame] = useState<M5Frame | null>(null);
  const [scan, setScan] = useState<M5Scan | null>(null);
  const [profile, setProfile] = useState<M5Profile | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [eventHeadSeq, setEventHeadSeq] = useState(0);
  const [eventTailSeq, setEventTailSeq] = useState(0);
  const eventTailRef = useRef(0);
  const eventLenRef = useRef(0);
  const [cal, setCal] = useState<M5Cal | null>(null);
  const [nvs, setNvs] = useState<M5Nvs | null>(null);
  const [recordStatus, setRecordStatus] = useState<M5RecordStatus | null>(null);
  const [history, setHistory] = useState<M5HistoryPoint[]>([]);
  const [lastError, setLastError] = useState<string | null>(null);
  const [url] = useState(() => getM5TelemetrySocketUrl());
  const [socketGen, setSocketGen] = useState(0);
  const socketRef = useRef<Socket | null>(null);
  const historyRef = useRef<M5HistoryPoint[]>([]);

  const reconnect = useCallback(() => {
    setSocketGen((g) => g + 1);
  }, []);

  const send = useCallback((cmd: M5Cmd) => {
    socketRef.current?.emit("m5/cmd", cmd);
  }, []);

  useEffect(() => {
    if (!active) return;

    setWsStatus("connecting");
    setLastError(null);
    historyRef.current = [];
    setHistory([]);

    const socket = io(url, {
      transports: ["polling", "websocket"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 400,
      reconnectionDelayMax: 4000,
    });
    socketRef.current = socket;

    socket.on("connect_error", (err: Error) => {
      setLastError(
        `M5 ブリッジ接続失敗 (${url}): ${err.message}。` +
          "Windows PC で `python tools/lab_debug.py` を起動し、" +
          "iPad は PC の LAN IP（:5173）で Hub を開いてください。"
      );
    });

    socket.on("connect", () => {
      setLastError(null);
      setWsStatus("connected");
    });

    socket.on("disconnect", () => {
      setWsStatus("disconnected");
    });

    const applyEventSnapshot = (raw: M5EventSnapshot | string[]) => {
      // 接続直後は全文。以降は m5/events/append だけ来る
      let lines: string[] = [];
      let seq = 0;
      if (Array.isArray(raw)) {
        // 旧: 新しい行が先頭。時系列に直す
        lines = raw.slice().reverse();
        seq = lines.length;
      } else if (raw && Array.isArray(raw.lines)) {
        lines = raw.lines.slice();
        seq = Number(raw.seq) || lines.length;
      }
      if (lines.length > M5_EVENTS_MAX) {
        lines = lines.slice(lines.length - M5_EVENTS_MAX);
      }
      setEvents(lines);
      const tail = seq;
      const head = lines.length ? tail - lines.length + 1 : 0;
      setEventHeadSeq(head);
      setEventTailSeq(tail);
      eventTailRef.current = tail;
      eventLenRef.current = lines.length;
    };

    socket.on("m5/hello", (payload: M5Hello) => {
      applyHello(
        payload ?? {},
        setStatus,
        setControl,
        setFrame,
        setScan,
        setProfile,
        applyEventSnapshot,
        setCal,
        setNvs,
        historyRef,
        setHistory
      );
      applyHelloRecord(payload ?? {}, setRecordStatus);
    });

    socket.on("m5/status", (payload: M5Status) => {
      setStatus(payload);
    });

    socket.on("m5/control", (payload: M5Control) => {
      setControl(payload);
    });

    socket.on("m5/frame", (payload: M5Frame | null) => {
      setFrame(payload);
      if (!payload) return;
      const next = [...historyRef.current, frameToHistory(payload)];
      if (next.length > HISTORY_MAX) next.splice(0, next.length - HISTORY_MAX);
      historyRef.current = next;
      setHistory(next);
    });

    socket.on("m5/scan", (payload: M5Scan) => {
      setScan(payload);
    });

    socket.on("m5/profile", (payload: M5Profile) => {
      setProfile(payload);
    });

    socket.on("m5/events", (payload: M5EventSnapshot | string[]) => {
      applyEventSnapshot(payload);
    });

    socket.on("m5/events/append", (payload: M5EventAppend) => {
      const batch = Array.isArray(payload?.lines) ? payload.lines : [];
      // 再送や hello 直後の重複は seq で捨てる
      const fresh = batch.filter((row) => Number(row.seq) > eventTailRef.current);
      if (!fresh.length) return;
      const tail = Number(fresh[fresh.length - 1]!.seq);
      const nextLen = Math.min(M5_EVENTS_MAX, eventLenRef.current + fresh.length);
      eventLenRef.current = nextLen;
      eventTailRef.current = tail;
      setEventTailSeq(tail);
      setEventHeadSeq(nextLen ? tail - nextLen + 1 : 0);
      setEvents((prev) => {
        const next = prev.concat(fresh.map((row) => String(row.text ?? "")));
        return next.length > M5_EVENTS_MAX ? next.slice(next.length - M5_EVENTS_MAX) : next;
      });
    });

    socket.on("m5/cal", (payload: M5Cal) => {
      setCal(payload);
    });

    socket.on("m5/nvs", (payload: M5Nvs) => {
      setNvs(payload);
    });

    socket.on("m5/record", (payload: M5RecordStatus) => {
      setRecordStatus(payload);
    });

    return () => {
      socketRef.current = null;
      socket.disconnect();
    };
  }, [active, url, socketGen]);

  return {
    wsStatus,
    url,
    status,
    control,
    frame,
    scan,
    profile,
    events,
    eventHeadSeq,
    eventTailSeq,
    cal,
    nvs,
    recordStatus,
    history,
    lastError,
    send,
    reconnect,
  };
}
