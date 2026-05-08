import { io, type Socket } from "socket.io-client";
import { SERVO_DAEMON_URL } from "@/shared/constants";

let socket: Socket | null = null;

/** robot-daemon（Flask-SocketIO）への共有接続 */
export function getServoDaemonSocket(): Socket {
  if (!socket) {
    socket = io(SERVO_DAEMON_URL, {
      transports: ["websocket"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
    });
  }
  return socket;
}

/** 初回接続完了まで待つ（fetch / move で利用） */
export function servoDaemonConnected(timeoutMs = 15_000): Promise<void> {
  const s = getServoDaemonSocket();
  if (s.connected) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => {
      cleanup();
      reject(new Error(`Servo daemon connection timeout (${timeoutMs}ms)`));
    }, timeoutMs);
    const onConnect = () => {
      cleanup();
      resolve();
    };
    const onConnectError = (err: Error) => {
      cleanup();
      reject(err);
    };
    const cleanup = () => {
      clearTimeout(t);
      s.off("connect", onConnect);
      s.off("connect_error", onConnectError);
    };
    s.once("connect", onConnect);
    s.once("connect_error", onConnectError);
  });
}
