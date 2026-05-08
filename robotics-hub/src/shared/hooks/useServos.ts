import { useState, useEffect, useRef } from "react";
import { fetchServos } from "@/shared/api/servoApi";
import { getServoDaemonSocket } from "@/shared/api/servoDaemonSocket";
import type { Servo } from "@/shared/types";

export function useServos() {
  const [servos, setServos] = useState<Servo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const initialConnectDone = useRef(false);

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

  useEffect(() => {
    const socket = getServoDaemonSocket();
    if (socket.connected) {
      initialConnectDone.current = true;
    }
    const onConnect = () => {
      if (!initialConnectDone.current) {
        initialConnectDone.current = true;
        return;
      }
      fetchServos()
        .then((data) => {
          setServos(data);
          setError(null);
        })
        .catch((err) => {
          console.error("Error refetching servos after reconnect:", err);
          setError(err instanceof Error ? err.message : "Unknown error");
        });
    };
    socket.on("connect", onConnect);
    return () => {
      socket.off("connect", onConnect);
    };
  }, []);

  return { servos, loading, error };
}
