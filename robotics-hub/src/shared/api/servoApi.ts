import { clamp } from "@/shared/utils";
import type { Servo, ServoMode } from "@/shared/types";
import { getServoDaemonSocket, servoDaemonConnected } from "@/shared/api/servoDaemonSocket";

interface ServoApiResponse {
  name?: string;
  ch?: number;
  logical_lo?: number;
  logical_hi?: number;
  physical_min?: number;
  physical_max?: number;
  last_logical?: number;
  default_logical?: number;
  last_physical?: number;
  default_physical?: number;
}

interface ServosApiData {
  servos?: ServoApiResponse[];
}

function formatServos(data: ServosApiData): Servo[] {
  const servosData = data.servos ?? [];
  return servosData.map((servo) => {
    const lo = servo.logical_lo ?? -90;
    const hi = servo.logical_hi ?? 90;
    const physMin = servo.physical_min ?? 0;
    const physMax = servo.physical_max ?? 180;
    const lastLogical = clamp(
      parseFloat(String(servo.last_logical ?? servo.default_logical ?? 0)),
      lo,
      hi
    );
    const lastPhysical = clamp(
      parseFloat(String(servo.last_physical ?? servo.default_physical ?? 90)),
      physMin,
      physMax
    );

    return {
      name: servo.name ?? "",
      ch: servo.ch ?? 0,
      logical_lo: lo,
      logical_hi: hi,
      physical_min: physMin,
      physical_max: physMax,
      last_logical: lastLogical,
      last_physical: lastPhysical,
    };
  });
}

/** moveServo / transitionServos の応答が交差しないよう直列化 */
let writeChain: Promise<unknown> = Promise.resolve();

function runExclusive<T>(fn: () => Promise<T>): Promise<T> {
  const next = writeChain.then(() => fn());
  writeChain = next.then(
    () => undefined,
    () => undefined
  );
  return next;
}

function waitServoList(timeoutMs: number): Promise<Servo[]> {
  const socket = getServoDaemonSocket();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("Timeout waiting for servo/list"));
    }, timeoutMs);
    const onList = (payload: unknown) => {
      cleanup();
      try {
        resolve(formatServos((payload ?? {}) as ServosApiData));
      } catch (e) {
        reject(e instanceof Error ? e : new Error(String(e)));
      }
    };
    const onErr = (payload: unknown) => {
      cleanup();
      const msg =
        typeof payload === "object" &&
        payload !== null &&
        "message" in payload &&
        typeof (payload as { message: unknown }).message === "string"
          ? (payload as { message: string }).message
          : "servo daemon error";
      reject(new Error(msg));
    };
    const cleanup = () => {
      clearTimeout(timer);
      socket.off("servo/list", onList);
      socket.off("error", onErr);
    };
    socket.once("servo/list", onList);
    socket.once("error", onErr);
  });
}

/**
 * サーボ一覧を取得（Socket.IO `servo/list`）
 */
export async function fetchServos(): Promise<Servo[]> {
  await servoDaemonConnected();
  const socket = getServoDaemonSocket();
  const pending = waitServoList(12_000);
  socket.emit("servo/list");
  return pending;
}

/** `/set` 相当（servo/result） */
export interface MoveServoResult {
  logical: number;
  physical: number;
}

/**
 * 単一サーボを動かす（`servo/set` → `servo/result`）
 */
export async function moveServo(
  ch: number,
  mode: ServoMode,
  angle: number
): Promise<MoveServoResult> {
  return runExclusive(async () => {
    await servoDaemonConnected();
    const socket = getServoDaemonSocket();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error("Timeout waiting for servo/result"));
      }, 12_000);
      const onResult = (payload: unknown) => {
        cleanup();
        const p = payload as {
          status?: string;
          result?: { logical?: unknown; physical?: unknown };
        };
        if (p?.status !== "ok" || !p.result) {
          reject(new Error("Invalid servo/result payload"));
          return;
        }
        const logical = Number(p.result.logical);
        const physical = Number(p.result.physical);
        if (!Number.isFinite(logical) || !Number.isFinite(physical)) {
          reject(new Error("Invalid servo/result: missing logical/physical"));
          return;
        }
        resolve({ logical, physical });
      };
      const onErr = (payload: unknown) => {
        cleanup();
        const msg =
          typeof payload === "object" &&
          payload !== null &&
          "message" in payload &&
          typeof (payload as { message: unknown }).message === "string"
            ? (payload as { message: string }).message
            : "servo error";
        reject(new Error(msg));
      };
      const cleanup = () => {
        clearTimeout(timer);
        socket.off("servo/result", onResult);
        socket.off("error", onErr);
      };
      socket.once("servo/result", onResult);
      socket.once("error", onErr);
      socket.emit("servo/set", {
        ch,
        mode,
        angle: parseFloat(String(angle)),
      });
    });
  });
}

/**
 * 複数サーボを動かす（`servo/set_multiple`）
 * 補間再生など高頻度のため、応答は待たず emit のみ（旧 fetch も未 await 運用と整合）
 */
export async function moveServos(
  servoAngles: Record<number, number>,
  mode: ServoMode = "logical"
): Promise<unknown> {
  await servoDaemonConnected();
  const socket = getServoDaemonSocket();
  const angles: Record<string, number> = {};
  for (const [ch, angle] of Object.entries(servoAngles)) {
    angles[String(ch)] = parseFloat(String(angle));
  }
  socket.emit("servo/set_multiple", { mode, angles });
  return { status: "ok" };
}

/**
 * 遷移開始（`servo/transition` → `servo/transition_started`）
 */
export async function transitionServos(
  angles: Record<string, number>,
  mode: ServoMode = "logical",
  duration = 5.0
): Promise<unknown> {
  return runExclusive(async () => {
    await servoDaemonConnected();
    const socket = getServoDaemonSocket();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error("Timeout waiting for servo/transition_started"));
      }, 15_000);
      const onStarted = (payload: unknown) => {
        cleanup();
        resolve(payload ?? {});
      };
      const onErr = (payload: unknown) => {
        cleanup();
        const msg =
          typeof payload === "object" &&
          payload !== null &&
          "message" in payload &&
          typeof (payload as { message: unknown }).message === "string"
            ? (payload as { message: string }).message
            : "servo error";
        reject(new Error(msg));
      };
      const cleanup = () => {
        clearTimeout(timer);
        socket.off("servo/transition_started", onStarted);
        socket.off("error", onErr);
      };
      socket.once("servo/transition_started", onStarted);
      socket.once("error", onErr);
      socket.emit("servo/transition", {
        mode,
        angles,
        duration,
      });
    });
  });
}
