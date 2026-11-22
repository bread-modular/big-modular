// Drives ../web/index.html in headless Chromium over the DevTools protocol: the
// channel strips in demo mode (real mouse drags on a knob and a fader), and the
// Web Serial path against a fake port that answers like the firmware (the page's
// DemoLink behind real streams). Not part of `make`: needs node >= 22 and chromium.
//
//   ../web/run.sh &                                  (or any server for ../web)
//   node web_check.mjs http://localhost:3000/ [folder for screenshots]
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const url = process.argv[2], shots = process.argv[3];
if (!url) { console.log("usage: node web_check.mjs <page url> [screenshot folder]"); process.exit(2); }
const chrome = spawn("chromium", ["--headless", "--disable-gpu", "--no-first-run", "--remote-debugging-port=9377", "--window-size=1500,1000", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0;
const waiting = new Map();
const cdp = (method, params = {}) => new Promise((res, rej) => { const i = ++id; waiting.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true, userGesture: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 600));
  return r.result.value;
};
let fails = 0;
const check = (ok, text) => { console.log((ok ? "ok   " : "FAIL ") + text); if (!ok) fails++; };
const shot = async (name) => { if (shots) writeFileSync(`${shots}/${name}.png`, Buffer.from((await cdp("Page.captureScreenshot")).data, "base64")); };
const mouse = (type, x, y, extra = {}) => cdp("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: type === "mouseReleased" ? 0 : 1, clickCount: 1, ...extra });
const centre = (sel) => evaluate(`(() => { const r = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
// press on the middle of `sel`, move `dy` pixels (up = negative) in steps, release
const drag = async (sel, dy) => {
  const [x, y] = await centre(sel);
  await mouse("mousePressed", x, y);
  for (let k = 1; k <= 6; k++) await mouse("mouseMoved", x, y + dy * k / 6);
  await mouse("mouseReleased", x, y + dy);
  await sleep(200);
};
const value = (pid) => evaluate(`[state.params.get("${pid}").value, state.link.values ? state.link.values.get("${pid}").v : null]`);
const row = (pid) => `state.detailRows.find((r) => r.p.id === "${pid}").row`;

try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200);
    try { target = (await (await fetch("http://127.0.0.1:9377/json")).json()).find((t) => t.type === "page"); } catch (e) {}
  }
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  const errors = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && waiting.has(m.id)) { const w = waiting.get(m.id); waiting.delete(m.id); m.error ? w.rej(new Error(m.error.message)) : w.res(m.result); }
    if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.text + " " + (m.params.exceptionDetails.exception?.description || ""));
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") errors.push(m.params.args.map((a) => a.value).join(" "));
  };
  await cdp("Runtime.enable");
  await cdp("Page.enable");

  // ---- demo mode: the mixer
  await cdp("Page.navigate", { url: url + "?demo" });
  await sleep(1500);
  check(await evaluate(`[...document.querySelectorAll(".strip .sname")].map((e) => e.textContent).join(" ")`) === "KICK MIX PARALLEL MASTER", "four strips: kick, mix, parallel, master");
  check(await evaluate(`[...document.querySelectorAll(".slot .slotname")].map((e) => e.textContent).join("|")`) === "Sub cut|Limiter|Low cut|Multiband|Compressor|Glue compressor|Cuts|Limiter", "effect slots per strip, no Other slot");
  check(await evaluate(`state.params.size`) === 75, "75 parameters");
  // every parameter has a place: a strip control, a slot switch, a slot's rows or the toolbar
  const placed = await evaluate(`(() => { const ids = new Set(TOOLBAR); for (const s of STRIPS) for (const i of [s.trim, s.send, s.fader, s.on, ...s.devices.map((d) => d.on)]) if (i) ids.add(i);
    for (const d of state.devices.values()) for (const sec of d.sections) for (const p of sec.params) ids.add(p.id); return [...state.params.keys()].filter((i) => !ids.has(i)); })()`);
  check(placed.length === 0, "every parameter is on a strip or in a slot" + (placed.length ? ": missing " + placed : ""));
  check(await evaluate(`document.querySelectorAll(".strip .knob").length === 4 && document.querySelectorAll(".strip .fader").length === 4`), "2 trim + 2 send knobs, 4 faders");
  check(await evaluate(`$("lat").textContent`) === "≈ 4.8 ms", "latency shown: " + await evaluate(`$("lat").textContent`));
  check(await evaluate(`$("unsaved").classList.contains("hidden")`), "no unsaved badge at start");
  check(await evaluate(`document.querySelector(".slot.sel .slotname").textContent + "|" + document.querySelector("#detail .dpath").textContent + "|" + document.querySelector("#detail .dname").textContent`) === "Sub cut|KICK|Sub cut", "first slot selected, its settings in the panel below");
  check(await evaluate(`document.querySelector("#detail").getBoundingClientRect().top > document.querySelector("#mixer").getBoundingClientRect().bottom - 1`), "panel sits under the mixer");
  await shot("web-strips");

  // ---- the panel: a row slider -> value box -> device -> slot summary -> badge
  await evaluate(`(() => { const s = ${row("k_hp_f")}.querySelector("input[type=range]"); s.value = 500; s.oninput(); })()`);
  await sleep(300);
  const hp = await value("k_hp_f");
  const hpBox = await evaluate(`${row("k_hp_f")}.querySelector(".num input").value`);
  check(Math.abs(hp[0] - 34.6) < 0.2 && hp[1] === hp[0] && hpBox === "34.6", "log slider at half way = 34.6 Hz on page and device: " + hp + " " + hpBox);
  check(await evaluate(`document.querySelector(".slot.sel .slotsum").textContent`) === "34.6 Hz · 24 dB/oct", "slot summary follows: " + await evaluate(`document.querySelector(".slot.sel .slotsum").textContent`));
  check(!(await evaluate(`$("unsaved").classList.contains("hidden")`)), "unsaved badge after a change");
  await evaluate(`${row("k_hp_f")}.querySelector("label").click()`);
  await sleep(200);
  check((await value("k_hp_f"))[1] === 25, "click on the name restores 25 Hz");

  // ---- slot switch, strip dimming, greyed rows
  await evaluate(`state.devices.get("k_hp").node.querySelector(".pwr").click()`);
  await sleep(200);
  check((await value("k_hp_on"))[1] === 0 && await evaluate(`state.devices.get("k_hp").node.classList.contains("off") && ${row("k_hp_f")}.classList.contains("off") && !document.querySelector("#detail .dhead input").checked`), "slot lamp switches Sub cut off: slot dimmed, rows greyed, panel switch off");
  await evaluate(`document.querySelector("#detail .dhead input").click()`);
  await sleep(200);
  check((await value("k_hp_on"))[1] === 1 && await evaluate(`state.devices.get("k_hp").node.querySelector(".pwr").classList.contains("on")`), "panel switch turns it back on, lamp lit");

  // ---- typed value, clamped by the device (master limiter)
  await evaluate(`state.devices.get("lim").node.click()`);
  await evaluate(`(() => { const b = ${row("lim_ceil")}.querySelector(".num input"); b.value = "5"; b.onchange(); })()`);
  await sleep(300);
  check((await value("lim_ceil"))[0] === 0 && await evaluate(`${row("lim_ceil")}.querySelector(".num input").value`) === "0.0", "typed +5 dB ceiling clamps to 0");
  check(await evaluate(`document.querySelector("#detail .dpath").textContent`) === "MASTER", "panel shows the master limiter");

  // ---- glue: enum buttons
  await evaluate(`state.devices.get("glue").node.click()`);
  await evaluate(`${row("glue_ratio")}.querySelectorAll("button")[2].click()`);
  await sleep(300);
  check((await value("glue_ratio"))[1] === 2 && await evaluate(`state.devices.get("glue").node.querySelector(".slotsum").textContent`) === "−10.0 dB · 10:1", "ratio button 10, summary: " + await evaluate(`state.devices.get("glue").node.querySelector(".slotsum").textContent`));

  // ---- multiband: three band cards, greyed with the switch
  await evaluate(`state.devices.get("mb").node.click()`);
  check(await evaluate(`document.querySelectorAll("#detail .band").length`) === 3 && await evaluate(`[...document.querySelectorAll("#detail .band h2")].map((e) => e.textContent).join("|")`) === "Low band|Mid band|High band", "multiband: three band cards");
  check(await evaluate(`state.detailRows.length`) === 24 && await evaluate(`document.querySelectorAll("#detail .band .bhead input[type=checkbox]").length`) === 3, "multiband: 9 common settings, 3 band switches + 15 band settings: " + await evaluate(`state.detailRows.length`));
  check(await evaluate(`${row("mb_lo_thr")}.classList.contains("off")`) === false, "band control not greyed");
  await shot("web-strips-multiband");
  await evaluate(`state.devices.get("mb").node.querySelector(".pwr").click()`);
  await sleep(200);
  check(await evaluate(`${row("mb_lo_thr")}.classList.contains("off") && ${row("mb_f1")}.classList.contains("off")`), "multiband off greys the band controls too");
  await evaluate(`state.devices.get("mb").node.querySelector(".pwr").click()`);

  // ---- strips: real mouse drags
  const trim0 = (await value("in_k_trim"))[0];
  await drag("#mixer > :nth-child(1) .sec.input .knob", -36);          // 36 of 180 px = +0.2 of +-24 dB
  const trim = await value("in_k_trim");
  check(trim0 === 0 && Math.abs(trim[0] - 9.5) <= 0.5 && trim[1] === trim[0], "kick trim knob dragged up 36 px: " + trim);
  check(await evaluate(`document.querySelector(".strip .sec.input .vbox input").value`) === trim[0].toFixed(1), "trim value box follows the knob");
  const [kx, ky] = await centre("#mixer > :nth-child(1) .sec.input .knob");
  await mouse("mousePressed", kx, ky); await mouse("mouseReleased", kx, ky);
  await mouse("mousePressed", kx, ky, { clickCount: 2 }); await mouse("mouseReleased", kx, ky, { clickCount: 2 });
  await sleep(200);
  check((await value("in_k_trim"))[1] === 0, "double-click puts the trim back to 0 dB");
  await drag("#mixer > :nth-child(1) .fader", 300);                    // far past the bottom
  const fad = await value("k_lvl");
  check(fad[0] === -60 && fad[1] === -60 && await evaluate(`document.querySelector(".strip .sec.fad .vbox input").value`) === "off", "kick fader dragged to the bottom: off (" + fad + ")");
  await evaluate(`(() => { const b = document.querySelector(".strip .sec.fad .vbox input"); b.value = "-3"; b.onchange(); })()`);
  await sleep(200);
  check((await value("k_lvl"))[1] === -3, "typed kick level -3 dB");
  await evaluate(`(() => { const b = document.querySelector(".strip .sec.send .vbox input"); b.value = "off"; b.onchange(); })()`);
  await sleep(200);
  check((await value("par_send_k"))[1] === -60 && await evaluate(`state.strips[2].strip.querySelector(".sec.input .info b").textContent`) === "off", "kick send typed off, the parallel strip shows it");
  // the same parameter in the strip and in the panel (kick channel view)
  await evaluate(`document.querySelector(".strip .shead").click()`);
  check(await evaluate(`state.detailRows.map((r) => r.p.id).join(" ")`) === "in_k_trim par_send_k k_lvl", "click on the strip name: trim, send and level as rows");
  await evaluate(`(() => { const s = ${row("par_send_k")}.querySelector("input[type=range]"); s.value = 900; s.oninput(); })()`);
  await sleep(200);
  check((await value("par_send_k"))[1] === -6 && await evaluate(`document.querySelector(".strip .sec.send .vbox input").value`) === "-6.0", "send row in the panel moves the strip's send too");

  // ---- parallel bus off
  await evaluate(`state.devices.get("par").node.click()`);
  check(await evaluate(`state.detailRows.map((r) => r.p.id).join(" ")`) === "par_thr par_ratio par_att par_rel par_makeup par_send_k par_send_m par_ret", "parallel bus: compressor settings, then sends and return");
  await evaluate(`state.devices.get("par").node.querySelector(".pwr").click()`);
  await sleep(300);
  check((await value("par_on"))[1] === 0 && await evaluate(`state.strips[2].strip.classList.contains("off") && ${row("par_thr")}.classList.contains("off")`), "parallel off: strip dimmed, its settings greyed");
  await evaluate(`state.devices.get("par").node.querySelector(".pwr").click()`);

  // ---- toolbar: save (right after a change: the change must go out before it), bypass, export, revert
  check(!(await evaluate(`$("unsaved").classList.contains("hidden")`)), "unsaved badge before Save");
  await evaluate(`$("save").click()`);
  await sleep(300);
  check(await evaluate(`$("unsaved").classList.contains("hidden")`), "badge gone after Save");
  await evaluate(`$("bypass").click()`);
  await sleep(300);
  check(await evaluate(`$("bypass").textContent === "BYPASSED" && $("unsaved").classList.contains("hidden") && document.body.classList.contains("bypassed")`), "bypass button, no unsaved badge");
  check(await evaluate(`$("lat").textContent`) === "≈ 2.3 ms", "bypass latency");
  await evaluate(`$("bypass").click()`);
  const text = await evaluate(`settingsText()`);
  check(text.includes("set glue_ratio 2\n") && text.includes("set k_lvl -3\n") && !text.includes("bypass") && !text.includes("mb_solo") && text.trim().split("\n").length === 73, "export: 73 saved settings, no setup aids");
  await evaluate(`state.devices.get("glue").node.click()`);
  await evaluate(`${row("glue_ratio")}.querySelectorAll("button")[0].click()`);
  await sleep(200);
  await evaluate(`$("revert").click()`);
  await sleep(300);
  check((await value("glue_ratio"))[0] === 2 && await evaluate(`${row("glue_ratio")}.querySelectorAll("button")[2].classList.contains("sel")`), "Revert restores the saved ratio");
  await shot("web-strips-changed");

  // ---- Web Serial path with a fake port
  await cdp("Page.navigate", { url });
  await sleep(800);
  check(await evaluate(`document.querySelectorAll(".strip").length === 0 && $("detail").childElementCount === 0`), "no mixer before connecting");
  await evaluate(`(() => {
    const fake = { opened: null, sent: [] };
    window.fake = fake;
    const port = {
      async open(o) {
        fake.opened = o;
        let push;
        this.readable = new ReadableStream({ start(c) { push = (t) => c.enqueue(new TextEncoder().encode(t)); fake.end = () => c.close(); } });
        const demo = new DemoLink((line) => {
          // answers in odd chunks, with CR LF and log noise, as a real port may
          const t = line + "\\r\\n";
          const cut = Math.floor(t.length / 3);
          push(t.slice(0, cut)); push(t.slice(cut));
        });
        fake.demo = demo;
        let rest = "";
        this.writable = new WritableStream({ write(chunk) {
          rest += new TextDecoder().decode(chunk);
          const lines = rest.split("\\n"); rest = lines.pop();
          for (const l of lines) { fake.sent.push(l); demo.send(l); }
        } });
        setTimeout(() => push("I (312) master: Starting master_0.1.0\\r\\n"), 30);
      },
      async close() { fake.closed = true; },
    };
    Object.defineProperty(navigator, "serial", { value: { requestPort: async (o) => { fake.filters = o; return port; } }, configurable: true });
  })()`);
  await evaluate(`$("connect").click()`);
  await sleep(1500);
  check(await evaluate(`$("linkText").textContent`) === "Connected", "serial: connected");
  check(await evaluate(`JSON.stringify(fake.filters)`) === '{"filters":[{"usbVendorId":12346}]}', "serial: Espressif USB filter");
  check(await evaluate(`state.params.size === 75 && document.querySelectorAll(".strip").length === 4 && document.querySelectorAll(".slot").length === 8`), "serial: mixer built from desc over the stream");
  check(await evaluate(`$("log").textContent.includes("Starting master_0.1.0")`), "serial: log line shown, not parsed");
  await evaluate(`state.devices.get("m_hp").node.click()`);
  await evaluate(`(() => { const s = ${row("m_hp_f")}.querySelector("input[type=range]"); for (const v of [100, 200, 300, 400]) { s.value = v; s.oninput(); } })()`);
  await sleep(300);
  const sets = await evaluate(`fake.sent.filter((l) => l.startsWith("set "))`);
  check(sets.length === 1 && sets[0].startsWith("set m_hp_f "), "serial: four slider moves in one tick = one set: " + sets);
  await drag("#mixer > :nth-child(6) .fader", 15);                     // master strip (flow arrows sit between the strips)
  const out = await evaluate(`[state.params.get("out_lvl").value, fake.demo.values.get("out_lvl").v, fake.sent.filter((l) => l.startsWith("set out_lvl ")).length]`);
  check(out[0] < 0 && out[0] > -20 && out[1] === out[0] && out[2] >= 1 && out[2] <= 7, "serial: master fader drag reaches the module: " + out);
  check(await evaluate(`fake.sent.filter((l) => l === "m").length`) > 10, "serial: meters polled");
  check(await evaluate(`$("cpu").textContent`) === "47 % (worst 58 %)", "serial: CPU shown");
  check(await evaluate(`document.querySelector(".strip .sec.fad .peak").textContent.endsWith(" dB") && document.querySelector(".strip .vlevel .fill").style.height !== ""`), "serial: strip meters move");
  await evaluate(`fake.end()`);
  await sleep(300);
  check(await evaluate(`$("linkText").textContent === "Not connected" && $("save").disabled && $("note").textContent.includes("unplugged")`), "serial: unplug detected");
  check(errors.length === 0, "no page errors" + (errors.length ? ": " + errors.join(" | ") : ""));
} catch (e) {
  console.log("FAIL exception: " + e.message);
  fails++;
} finally {
  chrome.kill();
}
console.log(fails ? `${fails} failed` : "all passed");
process.exit(fails ? 1 : 0);
