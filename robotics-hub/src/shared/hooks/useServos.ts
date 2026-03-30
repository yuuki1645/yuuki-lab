import { useState, useEffect } from "react";
import { fetchServos } from "@/shared/api/servoApi";
import type { Servo } from "@/shared/types";

export function useServos() {
  const [servos, setServos] = useState<Servo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadServos() {
      try {
        setLoading(true);
        const data = await fetchServos();
        setServos(data);
        setError(null);
      } catch (err) {
        console.error("Error fetching servos:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }

    loadServos();
  }, []);

  return { servos, loading, error };
}
