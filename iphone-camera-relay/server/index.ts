import path from "node:path";
import fs from "node:fs";
import express from "express";
import { createServer as createHttpServer } from "node:http";
import { createServer as createHttpsServer } from "node:https";
import { Server } from "socket.io";
import type { Socket } from "socket.io";
import type { IncomingMessage, ServerResponse } from "node:http";

const projectRoot = process.cwd();
const PORT = Number(process.env.PORT) || 5000;
const isDev = process.env.NODE_ENV !== "production";

function loadTlsOptions():
  | { key: Buffer; cert: Buffer }
  | null {
  const keyPath = path.join(projectRoot, "key.pem");
  const certPath = path.join(projectRoot, "cert.pem");
  if (!fs.existsSync(keyPath) || !fs.existsSync(certPath)) {
    return null;
  }
  return {
    key: fs.readFileSync(keyPath),
    cert: fs.readFileSync(certPath),
  };
}

function toBuffer(
  data: Buffer | ArrayBuffer | Uint8Array | unknown,
): Buffer | null {
  if (Buffer.isBuffer(data)) return data;
  if (data instanceof ArrayBuffer) return Buffer.from(data);
  if (data instanceof Uint8Array) return Buffer.from(data);
  return null;
}

function attachSocketRelay(io: Server): void {
  let latestFrame: Buffer | null = null;

  io.on("connection", (socket: Socket) => {
    if (latestFrame) {
      socket.emit("frame_update", latestFrame);
    }

    socket.on("camera_frame", (data: unknown) => {
      const buf = toBuffer(data);
      if (!buf || buf.length === 0) return;
      latestFrame = buf;
      socket.broadcast.emit("frame_update", buf);
    });
  });
}

function createNodeServer(
  app: express.Express,
  tls: { key: Buffer; cert: Buffer } | null,
):
  | ReturnType<typeof createHttpServer>
  | ReturnType<typeof createHttpsServer> {
  if (tls) {
    return createHttpsServer(
      tls,
      app as unknown as (req: IncomingMessage, res: ServerResponse) => void,
    );
  }
  return createHttpServer(
    app as unknown as (req: IncomingMessage, res: ServerResponse) => void,
  );
}

async function attachClientMiddleware(
  app: express.Express,
  httpServer:
    | ReturnType<typeof createHttpServer>
    | ReturnType<typeof createHttpsServer>,
): Promise<void> {
  if (isDev) {
    const { createServer: createViteServer } = await import("vite");
    const viteServer = await createViteServer({
      root: projectRoot,
      server: {
        middlewareMode: true,
        hmr: { server: httpServer },
      },
      appType: "spa",
    });
    app.use(viteServer.middlewares);

    process.on("SIGINT", () => {
      void viteServer.close();
    });
  } else {
    const clientDir = path.join(projectRoot, "dist", "client");
    app.use(express.static(clientDir));
    app.use((req, res, next) => {
      if (req.method !== "GET" || req.path.startsWith("/socket.io")) {
        next();
        return;
      }
      res.sendFile(path.join(clientDir, "index.html"));
    });
  }
}

async function main(): Promise<void> {
  const app = express();
  const tls = loadTlsOptions();

  if (!tls) {
    console.warn(
      "[camera-relay] cert.pem / key.pem が見つかりません。HTTP で起動します。",
    );
    console.warn(
      "[camera-relay] iPhone のカメラ利用には HTTPS が必要なため、ルートに cert.pem と key.pem を配置してください。",
    );
  }

  const httpServer = createNodeServer(app, tls);
  await attachClientMiddleware(app, httpServer);

  const io = new Server(httpServer, {
    cors: { origin: "*", methods: ["GET", "POST"] },
    maxHttpBufferSize: 10e6,
  });
  attachSocketRelay(io);

  httpServer.listen(PORT, "0.0.0.0", () => {
    const scheme = tls ? "https" : "http";
    console.log(
      `[camera-relay] ${scheme}://0.0.0.0:${PORT} （LAN からは PC の IP アドレスでアクセス）`,
    );
    console.log(`[camera-relay] iPhone: ${scheme}://<PCのIP>:${PORT}/camera`);
    console.log(`[camera-relay] PC表示: ${scheme}://<PCのIP>:${PORT}/monitor`);
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
