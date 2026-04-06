import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent } from "react";
import { moveServo } from "@/shared/api/servoApi";
import { SERVO_NAME_TO_CH } from "@/shared/constants";
import { clamp } from "@/shared/utils";
import type { Servo } from "@/shared/types";
import {
  limitsFor,
  readLegFromServos,
  servoName,
} from "../lib/servoUtils";
import type { ActiveDrag, JointKey, LegId, LegPose } from "../types";

const DRAG_SENSITIVITY = 0.32;

export function usePoseEditorControl(servos: Servo[], apiError: string | null) {
  const [left, setLeft] = useState<LegPose>({
    hip1: 0,
    hip2: 90,
    knee: 0,
    heel: 0,
    heelRoll: 0,
  });
  const [right, setRight] = useState<LegPose>({
    hip1: 0,
    hip2: 90,
    knee: 0,
    heel: 0,
    heelRoll: 0,
  });
  const [activeDrag, setActiveDrag] = useState<ActiveDrag | null>(null);

  const initRef = useRef(false);
  const dragRef = useRef<ActiveDrag | null>(null);
  const poseRef = useRef<{ L: LegPose; R: LegPose }>({ L: left, R: right });
  const apiTimers = useRef<
    Partial<Record<number, ReturnType<typeof setTimeout>>>
  >({});
  const moveSeqRef = useRef(0);
  const servosRef = useRef<Servo[]>(servos);

  useEffect(() => {
    poseRef.current = { L: left, R: right };
  }, [left, right]);

  useEffect(() => {
    servosRef.current = servos;
  }, [servos]);

  useEffect(() => {
    if (!servos.length || initRef.current) return;
    const L = readLegFromServos(servos, "L");
    const R = readLegFromServos(servos, "R");
    setLeft(L);
    setRight(R);
    poseRef.current = { L, R };
    initRef.current = true;
  }, [servos]);

  const setLegAngle = useCallback((leg: LegId, key: JointKey, v: number) => {
    const loHi = limitsFor(servosRef.current, leg, key);
    const clamped = clamp(v, loHi.lo, loHi.hi);
    if (leg === "L") {
      setLeft((p) => {
        const next = { ...p, [key]: clamped };
        poseRef.current = { ...poseRef.current, L: next };
        return next;
      });
    } else {
      setRight((p) => {
        const next = { ...p, [key]: clamped };
        poseRef.current = { ...poseRef.current, R: next };
        return next;
      });
    }
    return clamped;
  }, []);

  const pushServo = useCallback(
    (leg: LegId, key: JointKey, angle: number, immediate = false) => {
      if (apiError) return;

      const name = servoName(leg, key);
      const ch = SERVO_NAME_TO_CH[name];
      if (ch === undefined) return;

      const run = async () => {
        const seq = ++moveSeqRef.current;
        try {
          await moveServo(ch, "logical", angle);
        } catch (err) {
          if (seq !== moveSeqRef.current) return;
          window.alert(
            `サーボ指令エラー (${name}):\n${err instanceof Error ? err.message : String(err)}`
          );
        } finally {
          delete apiTimers.current[ch];
        }
      };

      if (immediate) {
        clearTimeout(apiTimers.current[ch]);
        void run();
        return;
      }
      clearTimeout(apiTimers.current[ch]);
      apiTimers.current[ch] = setTimeout(run, 95);
    },
    [apiError]
  );

  const flushDragPointerUp = useCallback(() => {
    const d = dragRef.current;
    if (!d) return;
    const snap = poseRef.current[d.leg][d.key];
    pushServo(d.leg, d.key, snap, true);
  }, [pushServo]);

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const cur = d.axis === "x" ? e.clientX : e.clientY;
      const delta = cur - d.startClient;
      const next = d.startAngle + delta * DRAG_SENSITIVITY * d.sign;
      console.log("next", next);
      const v = setLegAngle(d.leg, d.key, next);
      pushServo(d.leg, d.key, v, false);
    };

    const onUp = () => {
      flushDragPointerUp();
      dragRef.current = null;
      setActiveDrag(null);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [setLegAngle, pushServo, flushDragPointerUp]);

  const onArrowDown = useCallback(
    (e: PointerEvent, partial: Omit<ActiveDrag, "startClient" | "startAngle">) => {
      e.preventDefault();
      e.stopPropagation();
      const pose = poseRef.current[partial.leg];
      const startAngle = pose[partial.key];
      const startClient = partial.axis === "x" ? e.clientX : e.clientY;
      const next: ActiveDrag = {
        ...partial,
        startClient,
        startAngle,
      };
      dragRef.current = next;
      setActiveDrag(next);
      try {
        (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      } catch {
        /* noop */
      }
    },
    []
  );

  const readout = useMemo(() => ({ L: left, R: right }), [left, right]);

  return { readout, activeDrag, onArrowDown };
}
