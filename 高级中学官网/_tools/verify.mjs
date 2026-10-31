// 用 Chrome DevTools Protocol 验收官网：
//   1) 捕获页面 JS 异常 / console.error
//   2) 遍历所有路由，检查标题与关键节点是否渲染
//   3) 检查 HTML 里引用的图片是否 404
//   4) 模拟在留言板发一条留言，确认交互生效
// 用法： node _tools/verify.mjs
import http from "node:http";
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 9333;
const DIR = "凌汛素材/高级中学官网";
const FILE = "坨罗山高级中学官网.html";
const URL_BASE = "file:///O:/mirror/" + DIR.split("/").map(encodeURIComponent).join("/") + "/" + encodeURIComponent(FILE);
const PROFILE = "O:\\mirror\\.tmp-chrome";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function getJSON(path) {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: "127.0.0.1", port: PORT, path, timeout: 3000 }, (res) => {
      let d = "";
      res.on("data", (c) => (d += c));
      res.on("end", () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    });
    req.on("error", reject);
    req.on("timeout", () => req.destroy(new Error("timeout")));
  });
}

/* ---------------- 极简 CDP 客户端 ---------------- */
class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.handlers = []; }
  static async connect(url) {
    const ws = new WebSocket(url);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
    const c = new CDP(ws);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && c.pending.has(msg.id)) {
        const { resolve, reject } = c.pending.get(msg.id);
        c.pending.delete(msg.id);
        msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
      } else if (msg.method) {
        c.handlers.forEach((h) => h(msg));
      }
    };
    return c;
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); reject(new Error("cdp timeout: " + method)); } }, 15000);
    });
  }
  on(fn) { this.handlers.push(fn); }
  async eval(expr) {
    const r = await this.send("Runtime.evaluate", {
      expression: `(function(){ ${expr} })()`,
      returnByValue: true, awaitPromise: true,
    });
    if (r.exceptionDetails) throw new Error("eval threw: " + JSON.stringify(r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result.value;
  }
}

const chrome = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--allow-file-access-from-files",
  `--user-data-dir=${PROFILE}`, `--remote-debugging-port=${PORT}`,
  "--window-size=1280,900", "about:blank",
], { stdio: "ignore" });

const report = { jsErrors: [], routes: [], images: [], board: {}, passed: 0, failed: 0 };
const ok = (cond, label, extra = "") => {
  if (cond) { report.passed++; console.log("  PASS  " + label); }
  else { report.failed++; console.log("  FAIL  " + label + (extra ? "  -> " + extra : "")); }
};

try {
  let tabs = null;
  for (let i = 0; i < 80; i++) {
    try { tabs = await getJSON("/json/list"); if (tabs && tabs.length) break; } catch {}
    await sleep(250);
  }
  if (!tabs || !tabs.length) throw new Error("Chrome 调试端口没起来");
  const target = tabs.find((t) => t.type === "page") || tabs[0];

  const cdp = await CDP.connect(target.webSocketDebuggerUrl);
  cdp.on((msg) => {
    if (msg.method === "Runtime.exceptionThrown") {
      const d = msg.params.exceptionDetails;
      report.jsErrors.push(d.exception?.description || d.text);
    }
    if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
      report.jsErrors.push("console.error: " + msg.params.args.map((a) => a.value ?? a.description).join(" "));
    }
    if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error") {
      const e = msg.params.entry;
      if (/ERR_FILE_NOT_FOUND|Failed to load resource/.test(e.text)) report.images.push(e.url || e.text);
      else report.jsErrors.push("log: " + e.text);
    }
  });

  await cdp.send("Runtime.enable");
  await cdp.send("Log.enable");
  await cdp.send("Page.enable");

  console.log("\n=== 1. 首页 ===");
  const nav = await cdp.send("Page.navigate", { url: URL_BASE });
  if (nav && nav.errorText) console.log("  navigate error: " + nav.errorText);
  await sleep(3000);

  const diag = await cdp.eval(`
    return {
      url: location.href,
      ready: document.readyState,
      scripts: document.scripts.length,
      navHtml: document.getElementById("nav") ? document.getElementById("nav").innerHTML.length : -1
    };
  `);
  ok(diag.navHtml > 0, "页面脚本已执行（导航已渲染）", JSON.stringify(diag));

  const home = await cdp.eval(`
    return {
      title: document.title,
      nav: document.querySelectorAll("#nav a").length,
      services: document.querySelectorAll("#home-services .svc").length,
      news: document.querySelectorAll("#home-news li").length,
      gallery: document.querySelectorAll("#home-gallery img").length,
      slides: document.querySelectorAll(".slide").length,
      strips: document.querySelectorAll(".strip img").length,
      boardEntry: !!document.querySelector(".board-entry"),
      leftoverToken: document.body.innerHTML.indexOf("__BOARD_ENTRY__") >= 0
    };
  `);
  ok(home.title.includes("坨罗山高级中学"), "标题正确", home.title);
  ok(home.nav === 11, "主导航 11 项", String(home.nav));
  ok(home.services === 7, "服务入口 7 个", String(home.services));
  ok(home.news === 6, "首页资讯 6 条", String(home.news));
  ok(home.gallery === 4, "校园风光 4 张", String(home.gallery));
  ok(home.slides === 3, "轮播 3 张", String(home.slides));
  ok(home.strips === 2, "两张通栏图", String(home.strips));
  ok(home.boardEntry, "首页有留言板入口");
  ok(!home.leftoverToken, "占位标记已被替换");

  console.log("\n=== 2. 各栏目路由 ===");
  const routes = ["", "xuexiao", "news", "notice", "dangjian", "jiaoyan", "deyu",
                  "zhaosheng", "shenghuo", "shizi", "xiaoyuan", "liuyan"];
  for (const k of routes) {
    await cdp.eval(`location.hash = "#/${k}";`);
    await sleep(320);
    const r = await cdp.eval(`
      var home = document.getElementById("view-home");
      var page = document.getElementById("view-page");
      return {
        homeShown: home.style.display !== "none",
        pageShown: page.style.display !== "none",
        title: document.getElementById("pg-title").textContent,
        bodyLen: document.getElementById("pg-body").innerHTML.length,
        navOn: (document.querySelector("#nav a.on")||{}).textContent || ""
      };
    `);
    const label = k || "(首页)";
    const good = k === ""
      ? (r.homeShown && !r.pageShown)
      : (r.pageShown && !r.homeShown && r.bodyLen > 50);
    report.routes.push({ k: label, ...r });
    ok(good, "路由 #/" + label + " 正常渲染", JSON.stringify(r).slice(0, 160));
  }

  console.log("\n=== 3. 留言板 ===");
  await cdp.eval(`location.hash = "#/liuyan";`);
  await sleep(400);
  const board0 = await cdp.eval(`
    return {
      count: document.querySelectorAll("#bd-list .msg").length,
      counter: document.getElementById("bd-count").textContent,
      hasForm: !!document.getElementById("bd-send"),
      hasTip: !!document.querySelector(".board-tip"),
      subnavOn: (document.querySelector(".subnav a.on")||{}).textContent || "",
      replies: document.querySelectorAll(".msg .reply").length
    };
  `);
  ok(board0.count >= 10, "留言已渲染（" + board0.count + " 条）", String(board0.count));
  ok(board0.counter === String(board0.count), "统计数字与条数一致", board0.counter + " vs " + board0.count);
  ok(board0.hasForm, "发表表单存在");
  ok(board0.hasTip, "板规/话题提示存在");
  ok(board0.subnavOn === "留言板", "子导航高亮正确", board0.subnavOn);
  ok(board0.replies > 0, "有校方回复楼层", String(board0.replies));

  // 模拟发一条留言
  const posted = await cdp.eval(`
    var n0 = document.querySelectorAll("#bd-list .msg").length;
    document.getElementById("bd-name").value = "测试同学";
    document.getElementById("bd-id").value = "2026级";
    document.getElementById("bd-text").value = "这是一条自动化测试留言。";
    document.getElementById("bd-send").click();
    var first = document.querySelector("#bd-list .msg");
    return {
      n0: n0,
      count: document.querySelectorAll("#bd-list .msg").length,
      counter: document.getElementById("bd-count").textContent,
      firstNick: (first.querySelector(".nick")||{}).textContent || "",
      isMine: first.classList.contains("mine"),
      cleared: document.getElementById("bd-text").value === ""
    };
  `);
  ok(posted.count === posted.n0 + 1, "发表后条数 +1（" + posted.n0 + " → " + posted.count + "）", String(posted.count));
  ok(posted.counter === String(posted.count), "计数器同步", posted.counter);
  ok(posted.firstNick === "测试同学", "新留言置顶显示", posted.firstNick);
  ok(posted.isMine, "新留言标记为本人");
  ok(posted.cleared, "提交后清空输入框");
  report.board = { board0, posted };

  // 空内容不应提交
  const empty = await cdp.eval(`
    var before = document.querySelectorAll("#bd-list .msg").length;
    document.getElementById("bd-text").value = "   ";
    document.getElementById("bd-send").click();
    return { before: before, after: document.querySelectorAll("#bd-list .msg").length };
  `);
  ok(empty.before === empty.after, "空内容不产生留言", JSON.stringify(empty));

  console.log("\n=== 4. 图片引用 ===");
  const imgs = await cdp.eval(`
    location.hash = "";
    return null;
  `);
  await sleep(600);
  const imgCheck = await cdp.eval(`
    var list = [].slice.call(document.images).map(function(im){
      return { src: im.getAttribute("src"), ok: im.complete && im.naturalWidth > 0, w: im.naturalWidth };
    });
    return list;
  `);
  const broken = imgCheck.filter((i) => !i.ok);
  report.images = broken;
  ok(broken.length === 0, "首页图片全部加载成功（" + imgCheck.length + " 张）",
     broken.map((b) => b.src).join(", "));

  // ---------- 4b. 搜「一条小鱼」→ 余淼的个人主页 ----------
  console.log("\n=== 4b. 搜「一条小鱼」 ===");
  const siteUrl = await cdp.eval(`return location.href;`);
  await cdp.eval(`location.hash = "#/search?q=" + encodeURIComponent("一条小鱼");`);
  await sleep(700);
  const ym = await cdp.eval(`
    var body = document.getElementById("pg-body");
    var a = body ? body.querySelector('a[href*="余淼的网站"]') : null;
    return { text: body ? body.textContent.replace(/\\s+/g, " ").trim() : "",
             href: a ? a.getAttribute("href") : "",
             resolved: a ? a.href : "" };
  `);
  ok(!!ym.href, "搜「一条小鱼」出一条结果并带链接");
  ok(ym.href === "../余淼的网站/index.html", "链接是相对路径 " + ym.href);
  ok(ym.text.indexOf("1条结果") >= 0, "写着 1 条结果");
  ok(ym.text.indexOf("学生个人主页：一条小鱼") >= 0, "结果标题是「学生个人主页：一条小鱼」");
  ok(ym.text.indexOf("余淼") < 0, "搜索结果里不点名余淼（规则 5：点过去她自己说）");
  const ymTarget = decodeURIComponent(ym.resolved.replace(/^file:\/\/\//, "").replace(/\//g, "\\"));
  ok(fs.existsSync(ymTarget), "链接目标真实存在", ymTarget);

  await cdp.eval(`location.hash = "#/search?q=" + encodeURIComponent("一条小鱼"); return 1;`);
  await sleep(600);
  await cdp.send("Emulation.setDeviceMetricsOverride", { width: 1100, height: 760, deviceScaleFactor: 1, mobile: false });
  await sleep(300);
  const yshot = await cdp.send("Page.captureScreenshot", { format: "png" });
  const ypath = path.join(os.tmpdir(), "school-yitiaoxiaoyu.png");
  fs.writeFileSync(ypath, Buffer.from(yshot.data, "base64"));
  console.log("  搜索结果 -> " + ypath);

  if (fs.existsSync(ymTarget)) {
    await cdp.send("Page.navigate", { url: ym.resolved });
    await sleep(1600);
    const landed = await cdp.eval(`return { title: document.title };`);
    ok(/一条小鱼/.test(landed.title), "点进去落到她的站（标题「" + landed.title + "」）");
    await cdp.send("Page.navigate", { url: siteUrl });
    await sleep(900);
  }

  console.log("\n=== 5. JS 异常 ===");
  ok(report.jsErrors.length === 0, "无 JS 异常/报错", report.jsErrors.join(" | ").slice(0, 300));

  const tmpReport = path.join(os.tmpdir(), "school-verify-report.json");
  fs.writeFileSync(tmpReport, JSON.stringify(report, null, 2));
  console.log("\n汇总：PASS " + report.passed + " / FAIL " + report.failed);
  console.log("报告：" + tmpReport);
} catch (e) {
  console.error("验收脚本自身出错：", e.message);
  report.failed++;
} finally {
  try { chrome.kill(); } catch {}
  await sleep(400);
  try { fs.rmSync(PROFILE, { recursive: true, force: true }); } catch {}
  process.exit(report.failed ? 1 : 0);
}
