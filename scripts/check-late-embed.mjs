import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { extname, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { setTimeout as delay } from "node:timers/promises";

const root = resolve(new URL("..", import.meta.url).pathname);
const docs = join(root, "docs");
const shotDir = process.argv.includes("--screenshots")
  ? process.argv[process.argv.indexOf("--screenshots") + 1]
  : "";

const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".png": "image/png",
};

function startServer() {
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, "http://127.0.0.1");
    let pathname = decodeURIComponent(url.pathname).replace(/^\/+/, "");
    if (pathname === "" || pathname.endsWith("/")) pathname += "index.html";
    const file = resolve(docs, pathname);
    if (file !== docs && !file.startsWith(docs + "/")) {
      res.writeHead(403);
      res.end();
      return;
    }
    try {
      const data = await readFile(file);
      res.writeHead(200, { "content-type": types[extname(file)] || "application/octet-stream" });
      res.end(data);
    } catch {
      res.writeHead(404);
      res.end("missing");
    }
  });
  return new Promise((resolveListen) => {
    server.listen(0, "127.0.0.1", () => resolveListen(server));
  });
}

function launchChrome(userDataDir) {
  const chrome = spawn("/usr/bin/google-chrome", [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    `--user-data-dir=${userDataDir}`,
    "--remote-debugging-port=0",
    "about:blank",
  ], { stdio: ["ignore", "pipe", "pipe"] });
  const wsUrl = new Promise((resolveWs, reject) => {
    const timer = setTimeout(() => reject(new Error("Chrome did not open a DevTools port")), 15000);
    let buffer = "";
    const onExit = (code) => {
      clearTimeout(timer);
      reject(new Error(`Chrome exited before DevTools was ready (${code})`));
    };
    const onData = (buf) => {
      buffer += buf.toString();
      const match = buffer.match(/DevTools listening on (ws:\/\/\S+)/);
      if (!match) return;
      clearTimeout(timer);
      chrome.off("exit", onExit);
      resolveWs(match[1]);
    };
    chrome.stderr.on("data", onData);
    chrome.stdout.on("data", onData);
    chrome.once("exit", onExit);
  });
  return { chrome, wsUrl };
}

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.next = 1;
    this.pending = new Map();
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (!message.id || !this.pending.has(message.id)) return;
      const { resolve, reject } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    });
  }

  send(method, params = {}, sessionId) {
    const id = this.next++;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    this.ws.send(JSON.stringify(payload));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
}

async function evaluate(cdp, sessionId, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  }, sessionId);
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || "page evaluation failed");
  }
  return result.result.value;
}

async function poll(cdp, sessionId, expression, timeoutMs) {
  const start = Date.now();
  let last = null;
  while (Date.now() - start < timeoutMs) {
    last = await evaluate(cdp, sessionId, expression);
    if (last) return last;
    await delay(40);
  }
  throw new Error(`timed out waiting for ${expression}; last=${JSON.stringify(last)}`);
}

const server = await startServer();
const port = server.address().port;
const userDataDir = join(tmpdir(), `bf-late-embed-${process.pid}`);
const { chrome, wsUrl } = launchChrome(userDataDir);
let failed = false;

try {
  const browserWs = new WebSocket(await wsUrl);
  await new Promise((resolveOpen, reject) => {
    browserWs.addEventListener("open", resolveOpen);
    browserWs.addEventListener("error", () => reject(new Error("DevTools socket failed")));
  });
  const cdp = new Cdp(browserWs);
  const { targetId } = await cdp.send("Target.createTarget", {
    url: `http://127.0.0.1:${port}/late-embed-harness.html`,
  });
  const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  await cdp.send("Page.enable", {}, sessionId);
  await cdp.send("Runtime.enable", {}, sessionId);

  const early = await poll(cdp, sessionId, `(() => {
    const root = document.documentElement;
    if (!root.dataset.earlyNav || !root.dataset.earlyBookings) return null;
    if (root.dataset.earlyNav !== "no" || root.dataset.earlyBookings !== "no") {
      return { ready: true, bad: true, earlyNav: root.dataset.earlyNav || "", earlyBookings: root.dataset.earlyBookings || "" };
    }
    if (root.dataset.injected !== "yes") return null;
    const frame = document.querySelector("[data-bookings] iframe.bookings-frame");
    const fallback = document.querySelector("[data-bookings-fallback]");
    if (!frame || !fallback) return null;
    return {
      ready: true,
      bad: false,
      frames: document.querySelectorAll("[data-bookings] iframe").length,
      src: frame.src,
      title: frame.title,
      hidden: fallback.hidden,
      fallbackText: fallback.innerText,
    };
  })()`, 8000);

  if (early.bad) throw new Error(`snippet was present before injection: ${JSON.stringify(early)}`);
  if (early.frames !== 1) throw new Error(`expected one booking iframe, found ${early.frames}`);
  if (!early.src.includes("https://boltforgegaming.zohobookings.com/portal-embed#/boltforgegaming")) {
    throw new Error(`iframe src is ${early.src}`);
  }
  if (early.title !== "Book a visit with BoltForge Gaming") throw new Error(`iframe title is ${early.title}`);
  if (!early.hidden) throw new Error("booking fallback stayed visible after the iframe mounted");

  await evaluate(cdp, sessionId, `document.querySelector(".nav-toggle-bars").dispatchEvent(new MouseEvent("click", { bubbles: true }))`);
  const opened = await evaluate(cdp, sessionId, `(() => {
    const nav = document.querySelector(".nav");
    const toggle = document.querySelector(".nav-toggle");
    return {
      open: nav.classList.contains("is-open"),
      expanded: toggle.getAttribute("aria-expanded"),
      label: toggle.getAttribute("aria-label"),
    };
  })()`);
  if (!opened.open || opened.expanded !== "true" || opened.label !== "Close menu") {
    throw new Error(`menu did not open from the icon: ${JSON.stringify(opened)}`);
  }

  await evaluate(cdp, sessionId, `document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))`);
  const escaped = await evaluate(cdp, sessionId, `(() => {
    const toggle = document.querySelector(".nav-toggle");
    return {
      open: document.querySelector(".nav").classList.contains("is-open"),
      expanded: toggle.getAttribute("aria-expanded"),
      label: toggle.getAttribute("aria-label"),
    };
  })()`);
  if (escaped.open || escaped.expanded !== "false" || escaped.label !== "Open menu") {
    throw new Error(`Escape did not close the menu: ${JSON.stringify(escaped)}`);
  }

  await evaluate(cdp, sessionId, `document.querySelector(".nav-toggle").click()`);
  await evaluate(cdp, sessionId, `document.querySelector("main").click()`);
  const outside = await evaluate(cdp, sessionId, `document.querySelector(".nav").classList.contains("is-open")`);
  if (outside) throw new Error("a click outside the header left the menu open");

  const stillOne = await evaluate(cdp, sessionId, `document.querySelectorAll("[data-bookings] iframe").length`);
  if (stillOne !== 1) throw new Error(`booking iframe was mounted ${stillOne} times`);

  if (shotDir) {
    await mkdir(shotDir, { recursive: true });
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true,
    }, sessionId);
    await evaluate(cdp, sessionId, `document.querySelector(".nav-toggle").click()`);
    const menu = await evaluate(cdp, sessionId, `(() => {
      const link = document.querySelector("#site-nav a");
      const box = link.getBoundingClientRect();
      return {
        open: document.querySelector(".nav").classList.contains("is-open"),
        h: Math.round(box.height),
      };
    })()`);
    if (!menu.open || menu.h < 44) throw new Error(`menu screenshot state is wrong: ${JSON.stringify(menu)}`);
    const menuShot = await cdp.send("Page.captureScreenshot", { format: "png" }, sessionId);
    await writeFile(join(shotDir, "late_menu_mobile.png"), Buffer.from(menuShot.data, "base64"));

    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 1280,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    }, sessionId);
    await evaluate(cdp, sessionId, `(() => {
      document.documentElement.style.scrollBehavior = "auto";
      const frame = document.querySelector("iframe.bookings-frame");
      const header = document.querySelector(".site-header").getBoundingClientRect().height;
      const top = frame.getBoundingClientRect().top + window.scrollY - header - 12;
      window.scrollTo(0, top);
    })()`);
    await delay(1500);
    const frame = await evaluate(cdp, sessionId, `(() => {
      const iframe = document.querySelector("iframe.bookings-frame");
      const box = iframe.getBoundingClientRect();
      return {
        top: Math.round(box.top),
        h: Math.round(box.height),
        hidden: document.querySelector("[data-bookings-fallback]").hidden,
      };
    })()`);
    if (frame.h < 790 || frame.top < 0 || frame.top > 200 || !frame.hidden) {
      throw new Error(`iframe screenshot state is wrong: ${JSON.stringify(frame)}`);
    }
    const frameShot = await cdp.send("Page.captureScreenshot", { format: "png" }, sessionId);
    await writeFile(join(shotDir, "late_book_iframe.png"), Buffer.from(frameShot.data, "base64"));
    console.log(`screenshots in ${shotDir}`);
  }

  browserWs.close();
  console.log("late snippet: menu toggles and the booking iframe mounts");
} catch (error) {
  failed = true;
  console.error(error instanceof Error ? error.message : error);
} finally {
  chrome.kill();
  await new Promise((resolveClose) => server.close(resolveClose));
}

if (failed) process.exit(1);
