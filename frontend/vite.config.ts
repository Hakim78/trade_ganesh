import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import sirv from "sirv";
import fs from "node:fs";
import path from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";

/**
 * En développement (`npm run dev`), sert le dossier `../outputs` du projet sous `/data/`, comme le fera
 * nginx dans Docker. Le frontend ne connaît qu'une seule URL : /data/dashboard.json et /data/live/state.json.
 */
function serveOutputs(): Plugin {
  const outputs = path.resolve(__dirname, "..", "outputs");
  const handler = sirv(outputs, { dev: true, etag: false, maxAge: 0 });
  // Un fichier absent doit répondre 404 (comme nginx), pas retomber sur index.html.
  const middleware = (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    const urlPath = decodeURIComponent((req.url ?? "/").split("?")[0]);
    const file = path.join(outputs, urlPath);
    if (!file.startsWith(outputs) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.statusCode = 404;
      res.setHeader("Content-Type", "text/plain");
      res.end("not found");
      return;
    }
    res.setHeader("Cache-Control", "no-store");
    handler(req, res, next);
  };
  return {
    name: "serve-outputs",
    configureServer(server) {
      server.middlewares.use("/data", middleware);
    },
    configurePreviewServer(server) {
      server.middlewares.use("/data", middleware);
    },
  };
}

export default defineConfig({
  plugins: [react(), serveOutputs()],
  server: { port: 5173, host: true },
  build: { outDir: "dist", sourcemap: false },
});
