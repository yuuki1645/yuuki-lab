import { useEffect, useState } from "react";
import { mujocoFetchState } from "@/shared/api/mujocoSimApi";
import { servosFromMujocoState } from "@/shared/mujocoMapping";
import type { Servo } from "@/shared/types";

/**
 * MuJoCo の現在姿勢を、モーションエディタとポーズエディタが読む Servo 配列にする。
 * 実機のサーボには接続しない。
 */
export function useServoBackendData() {
  const [servos, setServos] = useState<Servo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setServos([]);
    setLoading(true);
    setError(null);

    async function load() {
      try {
        const state = await mujocoFetchState();
        if (!cancelled) {
          setServos(servosFromMujocoState(state));
        }
      } catch (err) {
        console.error("MuJoCo state load error:", err);
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
          setServos([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { servos, loading, error };
}
