import { useEffect, useState } from "react";
import { mujocoFetchState } from "@/shared/api/mujocoSimApi";
import { fetchServos } from "@/shared/api/servoApi";
import { servosFromMujocoState } from "@/shared/mujocoMapping";
import type { Servo, ServoBackendMode } from "@/shared/types";

export function useServoBackendData(mode: ServoBackendMode) {
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
        if (mode === "daemon") {
          const data = await fetchServos();
          if (!cancelled) {
            setServos(data);
          }
        } else {
          const state = await mujocoFetchState();
          if (!cancelled) {
            setServos(servosFromMujocoState(state));
          }
        }
      } catch (err) {
        console.error("Servo backend load error:", err);
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
  }, [mode]);

  return { servos, loading, error };
}
