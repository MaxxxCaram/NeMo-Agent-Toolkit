#!/usr/bin/env node
const http = require("http");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const PORT = parseInt(process.env.DASHBOARD_PORT || "3000", 10);
const MEMORY_DIR = process.env.MEMORY_DIR || path.join(process.env.HOME || "/home/ubuntu", ".openclaw-memory", "chats");
const NEMOCLAW_DIR = path.join(process.env.HOME || "/home/ubuntu", ".nemoclaw");
const OPENSHELL = process.env.OPENSHELL_BIN || "/home/ubuntu/.local/bin/openshell";

function safe(fn) { try { return fn(); } catch { return null; } }

function getSystemInfo() {
  const uptime = safe(() => execSync("uptime -p", { encoding: "utf-8" }).trim());
  const disk = safe(() => {
    const out = execSync("df -h / --output=size,used,avail,pcent", { encoding: "utf-8" });
    const line = out.trim().split("\n")[1].trim().split(/\s+/);
    return { total: line[0], used: line[1], avail: line[2], pct: line[3] };
  });
  const mem = safe(() => {
    const out = execSync("free -h --si", { encoding: "utf-8" });
    const line = out.trim().split("\n")[1].trim().split(/\s+/);
    return { total: line[1], used: line[2], free: line[3] };
  });
  const docker = safe(() => execSync("docker --version", { encoding: "utf-8" }).trim());
  const nodeVer = process.version;
  return { uptime, disk, mem, docker, node: nodeVer };
}

function getSandboxInfo() {
  const sandboxFile = path.join(NEMOCLAW_DIR, "sandboxes.json");
  const sandboxes = safe(() => JSON.parse(fs.readFileSync(sandboxFile, "utf-8")));
  const creds = safe(() => {
    const c = JSON.parse(fs.readFileSync(path.join(NEMOCLAW_DIR, "credentials.json"), "utf-8"));
    return { provider: c.provider, model: c.model, hasApiKey: !!c.nvidia_api_key, hasTgToken: !!c.telegram_bot_token };
  });
  const containers = safe(() =>
    execSync('docker ps --format "{{.Names}}|{{.Status}}|{{.Image}}"', { encoding: "utf-8" })
      .trim().split("\n").filter(Boolean).map((l) => { const p = l.split("|"); return { name: p[0], status: p[1], image: p[2] }; })
  );
  return { sandboxes, creds, containers };
}

function getTelegramBridgeInfo() {
  const pidFile = "/tmp/nemoclaw-services-my-assistant/telegram-bridge.pid";
  const logFile = "/tmp/nemoclaw-services-my-assistant/telegram-bridge.log";
  const pid = safe(() => fs.readFileSync(pidFile, "utf-8").trim());
  const running = pid ? safe(() => { process.kill(parseInt(pid), 0); return true; }) || false : false;
  const lastLogs = safe(() => {
    const content = fs.readFileSync(logFile, "utf-8");
    return content.split("\n").filter((l) => l.startsWith("[")).slice(-20);
  }) || [];
  return { pid, running, lastLogs };
}

function getMemoryStats() {
  if (!fs.existsSync(MEMORY_DIR)) return { chats: 0, totalMessages: 0, conversations: [] };
  const files = safe(() => fs.readdirSync(MEMORY_DIR).filter((f) => f.endsWith(".json"))) || [];
  let totalMessages = 0;
  const conversations = files.map((f) => {
    const chatId = f.replace(".json", "");
    const data = safe(() => JSON.parse(fs.readFileSync(path.join(MEMORY_DIR, f), "utf-8"))) || [];
    totalMessages += data.length;
    const lastMsg = data.length > 0 ? data[data.length - 1] : null;
    return {
      chatId,
      messageCount: data.length,
      lastActivity: lastMsg ? new Date(lastMsg.ts).toISOString() : null,
      preview: lastMsg ? lastMsg.content.slice(0, 80) : null,
    };
  }).sort((a, b) => (b.lastActivity || "").localeCompare(a.lastActivity || ""));
  return { chats: files.length, totalMessages, conversations };
}

function getConversation(chatId) {
  const file = path.join(MEMORY_DIR, `${chatId}.json`);
  return safe(() => JSON.parse(fs.readFileSync(file, "utf-8"))) || [];
}

function handleApi(req, res) {
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Access-Control-Allow-Origin", "*");

  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname === "/api/status") {
    return res.end(JSON.stringify({
      system: getSystemInfo(),
      sandbox: getSandboxInfo(),
      telegram: getTelegramBridgeInfo(),
      memory: getMemoryStats(),
      timestamp: new Date().toISOString(),
    }));
  }

  if (url.pathname === "/api/memory") {
    return res.end(JSON.stringify(getMemoryStats()));
  }

  if (url.pathname.startsWith("/api/conversation/")) {
    const chatId = url.pathname.split("/").pop();
    return res.end(JSON.stringify(getConversation(chatId)));
  }

  res.statusCode = 404;
  res.end(JSON.stringify({ error: "not found" }));
}

const HTML_PATH = path.join(__dirname, "index.html");

const server = http.createServer((req, res) => {
  if (req.url.startsWith("/api/")) return handleApi(req, res);

  if (req.url === "/" || req.url === "/index.html") {
    res.setHeader("Content-Type", "text/html; charset=utf-8");
    return res.end(fs.readFileSync(HTML_PATH));
  }

  res.statusCode = 404;
  res.end("Not found");
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`NemoClaw Dashboard running on http://0.0.0.0:${PORT}`);
});
