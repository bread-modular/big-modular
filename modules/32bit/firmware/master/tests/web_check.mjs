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
let fails = 0, dragData = null;
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
    if (m.method === "Input.dragIntercepted") dragData = m.params.data;
  };
  await cdp("Runtime.enable");
  await cdp("Page.enable");
  // a headless page counts as hidden: without this its timers get throttled after a few minutes
  await cdp("Emulation.setFocusEmulationEnabled", { enabled: true });
  await cdp("Page.bringToFront");

  // ---- demo mode: the mixer
  await cdp("Page.navigate", { url: url + "?demo" });
  await sleep(1500);
  check(await evaluate(`[...document.querySelectorAll(".strip .sname")].map((e) => e.textContent).join(" ")`) === "KICK MIX PARALLEL MASTER", "four strips: kick, mix, parallel, master");
  check(await evaluate(`[...document.querySelectorAll(".slot .slotname")].map((e) => e.textContent).join("|")`) === "Filter|Limiter|Filter|Multiband|Compressor|Glue compressor|Filter|Limiter", "effect slots per strip, no Other slot");
  check(await evaluate(`state.params.size`) === 106, "106 parameters");
  // every parameter has a place: a strip control, a slot switch, a slot's settings or the side panel
  const placed = await evaluate(`(() => { const ids = new Set(TOOLBAR); for (const s of STRIPS) for (const i of [s.trim, s.send, s.fader, s.on, s.order, s.mute, s.solo, ...s.devices.map((d) => d.on)]) if (i) ids.add(i);
    for (const d of state.devices.values()) for (const sec of d.sections) for (const p of sec.params) ids.add(p.id); return [...state.params.keys()].filter((i) => !ids.has(i)); })()`);
  check(placed.length === 0, "every parameter is on a strip or in a slot" + (placed.length ? ": missing " + placed : ""));
  // every setting of an effect has a control in its panel
  const unshown = await evaluate(`(() => { const miss = []; for (const d of state.devices.values()) { select(d.id); const shown = new Set(state.detailViews.map(([p]) => p.id));
    for (const sec of d.sections) for (const p of sec.params) if (!shown.has(p.id)) miss.push(d.id + ":" + p.id); } select("k_flt"); return miss; })()`);
  check(unshown.length === 0, "every effect setting has a control in the panel" + (unshown.length ? ": missing " + unshown : ""));
  check(await evaluate(`document.querySelectorAll(".strip svg.knob").length === 4 && document.querySelectorAll(".strip .fader").length === 4`), "2 trim + 2 send knobs, 4 faders");
  check(await evaluate(`$("lat").textContent`) === "≈ 4.8 ms", "latency shown: " + await evaluate(`$("lat").textContent`));
  check(await evaluate(`$("unsaved").classList.contains("hidden")`), "no unsaved badge at start");
  check(await evaluate(`document.querySelector(".slot.sel .slotname").textContent + "|" + document.querySelector("#detail .dpath").textContent + "|" + document.querySelector("#detail .dname").textContent`) === "Filter|KICK|Filter", "first slot selected, its settings in the panel below");
  const layout = await evaluate(`(() => { const d = $("detail").getBoundingClientRect(), m = $("mixer").getBoundingClientRect(), s = $("side").getBoundingClientRect(); return [d.top >= m.bottom - 1, s.left >= d.right, s.height, d.height, document.scrollingElement.scrollHeight <= innerHeight, innerHeight]; })()`);
  check(layout[0] && layout[1] && layout[2] === layout[5] && layout[3] === 400 && layout[4], "panel under the mixer, side panel on the right, full height, no page scroll: " + layout);
  await shot("web-filter");

  // ---- filter: drag the low cut point right and up, double-click the high cut point
  const dot = (cut) => evaluate(`(() => { const ch = state.detailRedraws, svg = document.querySelector("#detail .chart svg"), r = svg.getBoundingClientRect();
    const c = [...svg.querySelectorAll("circle")][${JSON.stringify(cut)} === "lc" ? 0 : 1]; return [r.x + +c.getAttribute("cx"), r.y + +c.getAttribute("cy")]; })()`);
  let [dx, dy] = await dot("lc");
  await mouse("mousePressed", dx, dy);
  for (let k = 1; k <= 6; k++) await mouse("mouseMoved", dx + 60 * k / 6, dy - 30 * k / 6);
  await mouse("mouseReleased", dx + 60, dy - 30);
  await sleep(300);
  const lcf = await value("k_flt_lc_f"), lcq = await value("k_flt_lc_q");
  check(lcf[0] > 40 && lcf[0] < 80 && lcf[1] === lcf[0] && lcq[0] > 1.2 && lcq[1] === lcq[0], "low cut point dragged: frequency and resonance up on page and device: " + lcf + " / " + lcq);
  check(await evaluate(`document.querySelector(".slot.sel .slotsum").textContent`).then((t) => t.startsWith("LC " + (lcf[0] >= 100 ? lcf[0].toFixed(0) : lcf[0].toFixed(1)) + " Hz · HC off")), "slot summary follows: " + await evaluate(`document.querySelector(".slot.sel .slotsum").textContent`));
  check(!(await evaluate(`$("unsaved").classList.contains("hidden")`)), "unsaved badge after a change");
  [dx, dy] = await dot("hc");
  await mouse("mousePressed", dx, dy); await mouse("mouseReleased", dx, dy);
  await mouse("mousePressed", dx, dy, { clickCount: 2 }); await mouse("mouseReleased", dx, dy, { clickCount: 2 });
  await sleep(300);
  check((await value("k_flt_hc_on"))[1] === 1 && await evaluate(`!document.querySelector("#detail .card:nth-child(2) .kn").classList.contains("off")`), "double-click on the H point turns the high cut on");
  await shot("web-filter-dragged");
  // knob value typed, label click = factory value
  const knobOf = (pid) => `state.detailCtls.find((c) => c.p.id === "${pid}").node`;
  await evaluate(`${knobOf("k_flt_hc_f")}.querySelector(".kvalue").click()`);
  await evaluate(`(() => { const i = ${knobOf("k_flt_hc_f")}.querySelector("input"); i.value = "1.2k"; i.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" })); })()`);
  await sleep(200);
  check((await value("k_flt_hc_f"))[1] === 1200 && await evaluate(`${knobOf("k_flt_hc_f")}.querySelector(".kvalue").textContent`) === "1.20k Hz", "typed 1.2k on the frequency knob: 1200 Hz");
  await evaluate(`${knobOf("k_flt_lc_f")}.querySelector(".klabel").click()`);
  await sleep(200);
  check((await value("k_flt_lc_f"))[1] === 25, "click on the knob's name restores 25 Hz");
  await drag(`#detail .card .kn:nth-child(2) svg`, -40);   // low cut resonance knob, up
  check((await value("k_flt_lc_q"))[0] > 0.71, "resonance knob dragged up: " + (await value("k_flt_lc_q")));

  // ---- slot switch: slot dimmed, panel controls greyed
  await evaluate(`state.devices.get("k_flt").node.querySelector(".pwr").click()`);
  await sleep(200);
  check((await value("k_flt_on"))[1] === 0 && await evaluate(`state.devices.get("k_flt").node.classList.contains("off") && ${knobOf("k_flt_lc_f")}.classList.contains("off") && !document.querySelector("#detail .dhead .tg").classList.contains("on")`), "slot lamp switches the filter off: slot dimmed, knobs greyed, panel switch off");
  await evaluate(`document.querySelector("#detail .dhead .tg").click()`);
  await sleep(200);
  check((await value("k_flt_on"))[1] === 1 && await evaluate(`state.devices.get("k_flt").node.querySelector(".pwr").classList.contains("on")`), "panel switch turns it back on, lamp lit");

  // ---- master limiter: auto release greys the release knob; typed ceiling clamps
  await evaluate(`state.devices.get("lim").node.click()`);
  await sleep(200);
  check(await evaluate(`document.querySelector("#detail .dpath").textContent`) === "MASTER" && await evaluate(`${knobOf("lim_rel")}.classList.contains("off")`), "master limiter: release greyed under auto release");
  check(await evaluate(`state.devices.get("lim").node.querySelector(".slotsum").textContent`) === "ceiling −1.0 dB · auto", "limiter summary says auto");
  await shot("web-limiter");
  await evaluate(`state.detailCtls.find((c) => c.p.id === "lim_auto").node.querySelector(".tg").click()`);
  await sleep(200);
  check((await value("lim_auto"))[1] === 0 && !(await evaluate(`${knobOf("lim_rel")}.classList.contains("off")`)) && await evaluate(`state.devices.get("lim").node.querySelector(".slotsum").textContent`) === "ceiling −1.0 dB · 100 ms", "auto off: release knob active, summary shows it");
  await evaluate(`${knobOf("lim_ceil")}.querySelector(".kvalue").click()`);
  await evaluate(`(() => { const i = ${knobOf("lim_ceil")}.querySelector("input"); i.value = "5"; i.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" })); })()`);
  await sleep(300);
  check((await value("lim_ceil"))[0] === 0, "typed +5 dB ceiling clamps to 0");

  // ---- order: drag the master limiter to the top, kick filter below its limiter, keyboard
  const slotDrag = async (id, dy) => {
    const [x, y] = await evaluate(`(() => { const r = state.devices.get("${id}").node.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
    await mouse("mousePressed", x, y);
    for (let k = 1; k <= 8; k++) await mouse("mouseMoved", x, y + dy * k / 8);
    await mouse("mouseReleased", x, y + dy);
    await sleep(300);
  };
  const slotNames = (strip) => evaluate(`[...state.strips[${strip}].devs.querySelectorAll(".slotname")].map((e) => e.textContent).join(" > ")`);
  await slotDrag("lim", -110);
  check((await value("o_order"))[1] === 4 && await slotNames(3) === "Limiter > Glue compressor > Filter", "master limiter dragged to the top: order 4, " + await slotNames(3));
  await slotDrag("k_flt", 50);
  check((await value("k_order"))[1] === 1 && await slotNames(0) === "Limiter > Filter", "kick filter dragged below the limiter: " + await slotNames(0));
  await evaluate(`state.devices.get("k_flt").node.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", altKey: true, bubbles: true }))`);
  await sleep(200);
  check((await value("k_order"))[1] === 0 && await slotNames(0) === "Filter > Limiter", "Alt + Up moves it back");
  check(await evaluate(`document.querySelector("#detail .dname").textContent`) === "Limiter", "a drag does not open the dragged slot");
  await evaluate(`state.devices.get("lim").node.click()`);
  await sleep(100);
  await shot("web-order");

  // ---- glue: ratio buttons, needle meter
  await evaluate(`state.devices.get("glue").node.click()`);
  await evaluate(`state.detailCtls.find((c) => c.p.id === "glue_ratio").node.querySelectorAll("button")[2].click()`);
  await sleep(400);
  check((await value("glue_ratio"))[1] === 2 && await evaluate(`state.devices.get("glue").node.querySelector(".slotsum").textContent`) === "−10.0 dB · 10:1", "ratio button 10, summary: " + await evaluate(`state.devices.get("glue").node.querySelector(".slotsum").textContent`));
  check(await evaluate(`document.querySelectorAll("#detail .chart").length`) === 3, "glue: curve, needle meter and timing graphs");
  await shot("web-glue");

  // ---- multiband: three band rows, split drag, greyed with the switch
  await evaluate(`state.devices.get("mb").node.click()`);
  await sleep(300);
  check(await evaluate(`document.querySelectorAll("#detail .bandrow").length`) === 3 && await evaluate(`[...document.querySelectorAll("#detail .bandrow .tg")].map((e) => e.textContent).join("|")`) === "LOW|MID|HIGH", "multiband: three band rows");
  const [sx, sy] = await evaluate(`(() => { const svg = document.querySelector("#detail .chart svg"), r = svg.getBoundingClientRect(), rect = svg.querySelectorAll("rect")[0]; return [r.x + +rect.getAttribute("x") + 5, r.y + +rect.getAttribute("y") + 7]; })()`);
  await mouse("mousePressed", sx, sy);
  for (let k = 1; k <= 5; k++) await mouse("mouseMoved", sx + 40 * k / 5, sy);
  await mouse("mouseReleased", sx + 40, sy);
  await sleep(300);
  const f1 = await value("mb_f1");
  check(f1[0] > 150 && f1[1] === f1[0], "low / mid split dragged right: " + f1);
  await shot("web-multiband");
  // the band rows keep their width when GR goes from one to two digits
  const rowW = (g) => evaluate(`(() => { state.detailMeters.forEach((u) => u({ gr_lo: ${g}, gr_mid: ${g}, gr_hi: ${g} }, performance.now())); return [...document.querySelectorAll("#detail .bandrow")].map((r) => r.getBoundingClientRect().width + "/" + r.lastChild.getBoundingClientRect().x).join(" "); })()`);
  const w1 = await rowW(0), w2 = await rowW(3.4), w3 = await rowW(18.7);
  check(w1 === w2 && w2 === w3, "multiband: band rows keep their layout at GR 0 / 3.4 / 18.7 dB: " + [w1, w3].join(" | "));
  await evaluate(`state.devices.get("mb").node.querySelector(".pwr").click()`);
  await sleep(200);
  check(await evaluate(`${knobOf("mb_lo_thr")}.classList.contains("off") && ${knobOf("mb_f1")}.classList.contains("off")`), "multiband off greys the band controls too");
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
  await evaluate(`(() => { const b = document.querySelector(".strip .col.send .vbox input"); b.value = "off"; b.onchange(); })()`);
  await sleep(200);
  check((await value("par_send_k"))[1] === -60 && await evaluate(`state.strips[2].strip.querySelector(".sec.input .info b").textContent`) === "off", "kick send typed off, the parallel strip shows it");
  // the same parameter on the strip and in the panel (kick channel view)
  await evaluate(`document.querySelector(".strip .shead").click()`);
  check(await evaluate(`state.detailCtls.map((c) => c.p.id).join(" ")`) === "in_k_trim par_send_k k_lvl", "click on the strip name: trim, send and level as knobs");
  await evaluate(`(() => { const p = state.params.get("par_send_k"); userSet(p, -6); })()`);
  await sleep(200);
  check((await value("par_send_k"))[1] === -6 && await evaluate(`document.querySelector(".strip .col.send .vbox input").value`) === "-6.0", "send in the panel moves the strip's send too");
  await shot("web-channel");

  // ---- parallel bus off
  await evaluate(`state.devices.get("par").node.click()`);
  check(await evaluate(`state.detailCtls.map((c) => c.p.id).join(" ")`) === "par_thr par_ratio par_makeup par_att par_rel par_send_k par_send_m par_ret", "parallel bus: compressor knobs, then sends and return");
  await shot("web-parallel");
  await evaluate(`state.devices.get("par").node.querySelector(".pwr").click()`);
  await sleep(300);
  check((await value("par_on"))[1] === 0 && await evaluate(`state.strips[2].strip.classList.contains("off") && ${knobOf("par_thr")}.classList.contains("off")`), "parallel off: strip dimmed, its settings greyed");
  await evaluate(`state.devices.get("par").node.querySelector(".pwr").click()`);

  // ---- the panel keeps its height in a smaller window
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1300, height: 800, deviceScaleFactor: 1, mobile: false });
  await sleep(300);
  check(await evaluate(`$("detail").getBoundingClientRect().height`) === 400 && await evaluate(`$("side").getBoundingClientRect().height`) === 800, "1300 x 800: panel still 400 px, side panel full height");
  await shot("web-small");
  // short faders: the shown scale labels never overlap
  const overlap = await evaluate(`(() => { let worst = 99; for (const f of document.querySelectorAll(".fader")) { const ys = [...f.querySelectorAll(".ftick:not(.hide) span")].map((s) => s.getBoundingClientRect()).sort((a, b) => a.y - b.y); for (let i = 1; i < ys.length; i++) worst = Math.min(worst, ys[i].y - ys[i - 1].bottom); } return worst; })()`);
  check(overlap >= 0, "1300 x 800: fader scale labels apart, closest gap " + overlap.toFixed(1) + " px");
  await cdp("Emulation.clearDeviceMetricsOverride");
  await sleep(200);

  // ---- side panel: save (right after a change: the change must go out before it), bypass, export, revert
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
  check(text.includes("set glue_ratio 2\n") && text.includes("set k_lvl -3\n") && !text.includes("bypass") && !text.includes("mb_solo") && !text.includes("k_off") && !text.includes("map ") && text.trim().split("\n").length === 97, "export: 97 saved settings, no setup aids, no mappings yet");
  await evaluate(`state.devices.get("glue").node.click()`);
  await evaluate(`state.detailCtls.find((c) => c.p.id === "glue_ratio").node.querySelectorAll("button")[0].click()`);
  await sleep(200);
  await evaluate(`$("revert").click()`);
  await sleep(300);
  check((await value("glue_ratio"))[0] === 2 && await evaluate(`state.detailCtls.find((c) => c.p.id === "glue_ratio").node.querySelectorAll("button")[2].classList.contains("sel")`), "Revert restores the saved ratio");


  // ---- the module's panel: drag to CV / MODE, ranges, off / solo, LED, saved with the settings
  const dnd = (fromExpr, zoneSrc) => evaluate(`(() => { const from = ${fromExpr}, zone = document.querySelector('.drop[data-src="${zoneSrc}"]'), dt = new DataTransfer();
    const ev = (n, t) => n.dispatchEvent(new DragEvent(t, { bubbles: true, cancelable: true, dataTransfer: dt }));
    ev(from, "dragstart"); const over = !ev(zone, "dragover"); const cls = zone.className; ev(zone, "drop"); ev(from, "dragend"); return [over, cls]; })()`);
  const maps = () => evaluate(`[state.maps.map((m) => [m.src, m.id, m.a, m.b].join(" ")).join(" | "), state.link.maps.map((m) => [m.src, m.id, m.a, m.b].join(" ")).join(" | ")]`);
  check(await evaluate(`document.querySelectorAll("#tab-panel .pcard").length === 4 && $("tab-panel").hidden`), "Panel tab: CV 1, CV 2, MODE, LED cards, hidden at first");
  await evaluate(`state.devices.get("glue").node.click()`);
  await sleep(100);
  const [accepted, zoneCls] = await dnd(`state.detailCtls.find((c) => c.p.id === "glue_thr").node.querySelector(".klabel")`, "cv1");
  await sleep(300);
  let mp = await maps();
  check(accepted && zoneCls.includes("can") && mp[0] === "cv1 glue_thr -40 0" && mp[1] === mp[0], "glue threshold dragged onto CV 1: the whole range, " + mp);
  check(!(await evaluate(`$("tab-panel").hidden`)) && (await value("glue_thr"))[0] === -20, "the Panel tab opens; the knob (demo: half way) sets −20 dB: " + (await value("glue_thr")));
  check(await evaluate(`state.detailCtls.find((c) => c.p.id === "glue_thr").node.querySelector(".klabel").dataset.maps`) === "CV1" && await evaluate(`$("mapCount").textContent`) === "1", "CV1 badge on the knob's name, count on the tab");
  await evaluate(`(() => { const i = document.querySelector('.drop[data-src="cv1"] .prow input'); i.value = "-30"; i.onchange(); })()`);
  await sleep(300);
  mp = await maps();
  check(mp[0] === "cv1 glue_thr -30 0" && mp[1] === mp[0] && (await value("glue_thr"))[0] === -15, "range typed: −30 → 0 dB, value −15: " + mp);
  check(await evaluate(`document.querySelector('.drop[data-src="cv1"] .prow .now').textContent`) === "−15.0 dB", "the row shows the value now");
  const [refused] = await dnd(`state.detailCtls.find((c) => c.p.id === "glue_ratio").node.querySelector(".klabel")`, "mode");
  await sleep(300);
  check(!refused && (await maps())[0] === "cv1 glue_thr -30 0", "a choice is not taken by MODE");
  await evaluate(`state.devices.get("lim").node.click()`);
  await sleep(100);
  const [laOk] = await dnd(`state.detailCtls.find((c) => c.p.id === "lim_la").node.querySelector(".klabel")`, "cv2");
  check(!laOk, "look-ahead is not taken by a knob");
  // strip off / solo
  await evaluate(`state.strips[0].strip.querySelector(".mb.off").click()`);
  await sleep(300);
  check((await value("k_off"))[1] === 1 && await evaluate(`state.strips[0].strip.classList.contains("silent") && !state.strips[1].strip.classList.contains("silent")`), "kick OFF: on the module, kick strip silent");
  await evaluate(`state.strips[0].strip.querySelector(".mb.off").click()`);
  await evaluate(`state.strips[1].strip.querySelector(".mb.solo").click()`);
  await sleep(300);
  check((await value("m_solo"))[1] === 1 && await evaluate(`[0, 1, 2, 3].map((i) => state.strips[i].strip.classList.contains("silent")).join()`) === "true,false,true,false", "mix solo: kick and parallel silent, master not");
  await evaluate(`state.strips[1].strip.querySelector(".mb.solo").click()`);
  // MODE: the kick's OFF button and Bypass onto MODE; click (default) / push / hold, one at a time
  await dnd(`state.strips[0].strip.querySelector(".mb.off")`, "mode");
  // the drag opens the Panel tab: Bypass must stay on screen then, or the browser drops the drag
  check(await evaluate(`showTab("panel"), !$("bypass").closest(".tabbody") && $("bypass").offsetParent !== null`), "Bypass stays visible with the Panel tab open");
  await dnd(`$("bypass")`, "mode");
  await sleep(300);
  mp = await maps();
  check(mp[0] === "cv1 glue_thr -30 0 | mode k_off 1 0 | mode bypass 1 0" && mp[1] === mp[0], "kick OFF and bypass onto MODE: " + mp);
  const modeCard = `document.querySelectorAll("#tab-panel .pcard")[2]`;
  const actSel = () => evaluate(`[...${modeCard}.querySelectorAll(".psub .seg button")].map((b) => b.textContent + (b.classList.contains("sel") ? "*" : "")).join(",")`);
  const modeLamp = () => evaluate(`${modeCard}.querySelector(".phead .lamp").classList.contains("on")`);
  check(await actSel() === "Click*,Hold,Push" && await evaluate(`document.querySelectorAll("#tab-panel .psub").length`) === 1, "MODE: one way to press at a time, Click selected: " + await actSel());
  await evaluate(`${modeCard}.querySelector(".psub .mini").click()`);
  await sleep(400);
  check((await value("k_off"))[0] === 1 && (await value("bypass"))[0] === 1 && await modeLamp(), "Press: kick off + bypass, MODE lamp lit");
  await evaluate(`${modeCard}.querySelector(".psub .mini").click()`);
  await sleep(400);
  check((await value("k_off"))[0] === 0 && (await value("bypass"))[0] === 0 && !(await modeLamp()), "Press again: back");
  await evaluate(`${modeCard}.querySelectorAll(".psub .seg button")[2].click()`);
  await sleep(300);
  check((await value("mode_act"))[1] === 2 && await actSel() === "Click,Hold,Push*" && await evaluate(`${modeCard}.querySelector(".psub .mini").textContent`) === "Hold", "Push selected on the module, the page button becomes Hold");
  await evaluate(`${modeCard}.querySelector(".psub .mini").dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }))`);
  await sleep(400);
  check((await value("k_off"))[0] === 1 && await modeLamp(), "push: over while the page button is down");
  await evaluate(`(() => { const b = ${modeCard}.querySelector(".psub .mini"); b.dispatchEvent(new PointerEvent("pointerup", { bubbles: true })); b.click(); })()`);
  await sleep(400);
  check((await value("k_off"))[0] === 0 && !(await modeLamp()), "push: back on the release, the click after it does nothing");
  await evaluate(`${modeCard}.querySelectorAll(".psub .seg button")[1].click()`);
  await sleep(300);
  check((await value("mode_act"))[1] === 1 && await actSel() === "Click,Hold*,Push", "Hold selected");
  await evaluate(`[...document.querySelectorAll('.drop[data-src="mode"] .prow')[0].querySelectorAll('.seg button')][1].click()`);
  await sleep(300);
  check((await maps())[0].includes("mode k_off 0 0"), "MODE value switched to OFF");
  // LED
  await evaluate(`(() => { const s = document.querySelector("#tab-panel .ledrow select"); s.value = 4; s.onchange(); })()`);
  await sleep(300);
  check((await value("led_mode"))[1] === 4, "LED shows MODE");
  await shot("web-panel");
  // saved with the settings, back after Revert, in the exported file
  await evaluate(`$("save").click()`);
  await sleep(300);
  await evaluate(`document.querySelector('.drop[data-src="cv1"] .prow .mini:last-child').click()`);
  await sleep(300);
  check((await maps())[0] === "mode k_off 0 0 | mode bypass 1 0" && !(await evaluate(`$("unsaved").classList.contains("hidden")`)), "× takes it off (unsaved)");
  await evaluate(`$("revert").click()`);
  await sleep(400);
  mp = await maps();
  check(mp[0] === "cv1 glue_thr -30 0 | mode k_off 0 0 | mode bypass 1 0" && (await value("mode_act"))[1] === 1, "Revert brings the saved mappings back: " + mp);
  const ptext = await evaluate(`settingsText()`);
  check(ptext.includes("set led_mode 4\n") && ptext.includes("set mode_act 1\n") && ptext.includes("map cv1 glue_thr -30 0\nmap mode k_off 0\nmap mode bypass 1\n"), "export: LED, MODE hold and mappings in the file");
  await evaluate(`(() => { window.confirm = () => true; $("factory").click(); })()`);
  await sleep(400);
  check((await maps())[0] === "" && await evaluate(`document.querySelectorAll("#tab-panel .prow").length`) === 0, "Factory: no mappings");
  await evaluate(`$("revert").click()`);
  await sleep(300);
  await evaluate(`showTab("setup")`);

  // ---- Web Serial path with a fake port
  await cdp("Page.navigate", { url });
  await sleep(800);
  check(await evaluate(`document.querySelectorAll(".strip").length === 0 && $("detail").childElementCount === 0`), "no mixer before connecting");
  await shot("web-start");
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
  check(await evaluate(`state.params.size === 106 && document.querySelectorAll(".strip").length === 4 && document.querySelectorAll(".slot").length === 8`), "serial: mixer built from desc over the stream");
  check(await evaluate(`$("log").textContent.includes("Starting master_0.1.0")`), "serial: log line shown, not parsed");
  await evaluate(`state.devices.get("m_flt").node.click()`);
  await evaluate(`(() => { const p = state.params.get("m_flt_lc_f"); for (const v of [50, 60, 70, 80]) userSet(p, v); })()`);
  await sleep(300);
  const sets = await evaluate(`fake.sent.filter((l) => l.startsWith("set "))`);
  check(sets.length === 1 && sets[0] === "set m_flt_lc_f 80", "serial: four moves in one tick = one set: " + sets);
  await drag("#mixer > :nth-child(6) .fader", 15);                     // master strip (flow arrows sit between the strips)
  const out = await evaluate(`[state.params.get("out_lvl").value, fake.demo.values.get("out_lvl").v, fake.sent.filter((l) => l.startsWith("set out_lvl ")).length]`);
  check(out[0] < 0 && out[0] > -20 && out[1] === out[0] && out[2] >= 1 && out[2] <= 7, "serial: master fader drag reaches the module: " + out);
  check(await evaluate(`fake.sent.filter((l) => l === "m").length`) > 10, "serial: meters polled");
  check(await evaluate(`$("cpu").textContent`) === "47 % (worst 58 %)", "serial: CPU shown");
  check(await evaluate(`document.querySelector(".strip .sec.fad .peak").textContent.endsWith(" dB") && document.querySelector(".strip .vlevel .fill").style.height !== ""`), "serial: strip meters move");
  await evaluate(`fake.end()`);
  await sleep(300);
  check(await evaluate(`$("linkText").textContent === "Not connected" && $("save").disabled && $("note").textContent.includes("unplugged")`), "serial: unplug detected");

  // ---- touch screen: hold a control, the sheet attaches it
  await cdp("Emulation.setDeviceMetricsOverride", { width: 412, height: 900, deviceScaleFactor: 2, mobile: true });
  await cdp("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 2 });
  await cdp("Page.navigate", { url: url + "?demo" });
  await sleep(1500);
  await evaluate(`state.devices.get("glue").node.scrollIntoView(); state.devices.get("glue").node.click()`);
  await sleep(200);
  await evaluate(`state.detailCtls.find((c) => c.p.id === "glue_makeup").node.scrollIntoView({ block: "center" })`);
  await sleep(200);
  const [tx, ty] = await evaluate(`(() => { const r = state.detailCtls.find((c) => c.p.id === "glue_makeup").node.querySelector("svg").getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
  const before = (await value("glue_makeup"))[0];
  await cdp("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: tx, y: ty }] });
  await cdp("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: tx, y: ty - 3 }] });
  await sleep(1000);
  await cdp("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await sleep(200);
  check(!(await evaluate(`$("sheet").hidden`)) && (await value("glue_makeup"))[0] === before, "touch: holding the make-up knob opens the sheet (it stays open after the finger lifts), the value stays");
  check(await evaluate(`[...$("sheetBtns").children].map((b) => b.textContent + (b.disabled ? "-" : "+")).join(",")`) === "CV 1+,CV 2+,MODE-", "sheet: two knobs, no MODE for a level");
  await shot("web-touch-sheet");
  await sleep(400);  // the finger's own click is over
  await evaluate(`$("sheetBtns").children[1].click()`);
  await sleep(300);
  check(await evaluate(`$("sheet").hidden && state.maps.map((m) => m.src + " " + m.id).join()`) === "cv2 glue_makeup" && !(await evaluate(`$("tab-panel").hidden`)), "touch: CV 2 tapped, attached, Panel tab shown");
  // a quick tap on a switch still switches it
  const [bx, by] = await evaluate(`(() => { const b = state.strips[1].strip.querySelector(".mb.off"); b.scrollIntoView({ block: "center" }); const r = b.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
  await cdp("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: bx, y: by }] });
  await cdp("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await sleep(300);
  check((await value("m_off"))[1] === 1, "touch: a tap on the mix OFF switches it");
  check(await evaluate(`document.scrollingElement.scrollWidth <= innerWidth + 1`), "412 px wide: no sideways page scroll (" + await evaluate(`document.scrollingElement.scrollWidth`) + ")");
  await shot("web-touch");
  await cdp("Emulation.setTouchEmulationEnabled", { enabled: false });
  await cdp("Emulation.clearDeviceMetricsOverride");
  // ---- a real mouse drag through the browser's drag and drop: copy, not link (Wayland has no link
  // action and refused the drop), onto CV 2. Last: Page.navigate hangs after an intercepted drag.
  await evaluate(`state.devices.get("glue").node.click()`);
  await sleep(100);
  await cdp("Input.setInterceptDrags", { enabled: true });
  const [lx, ly] = await centre(`#detail .card .kn:nth-child(2) .klabel`);
  const knobPid = await evaluate(`document.querySelector("#detail .card .kn:nth-child(2) .klabel").dataset.pid`);
  await mouse("mousePressed", lx, ly);
  for (let k = 1; k <= 6; k++) await mouse("mouseMoved", lx + 6 * k, ly + 3 * k);
  await sleep(200);
  const [zx, zy] = await centre(`.drop[data-src="cv2"]`);
  check(dragData && dragData.dragOperationsMask === 1 && dragData.items[0].data === knobPid, "native drag: copy only, carries the setting: " + JSON.stringify(dragData));
  if (dragData) {
    for (const type of ["dragEnter", "dragOver", "dragOver", "drop"]) { await cdp("Input.dispatchDragEvent", { type, x: zx, y: zy, data: dragData }); await sleep(30); }
  }
  await mouse("mouseReleased", zx, zy);
  await cdp("Input.setInterceptDrags", { enabled: false });
  await sleep(300);
  check((await maps())[0].includes("cv2 " + knobPid + " "), "native drag onto CV 2 stays: " + (await maps())[0]);
  // right-click a control: the attach sheet, as a hold on a touch screen
  const [rx, ry] = await centre(`#detail .card .kn:nth-child(2) .klabel`);
  await mouse("mousePressed", rx, ry, { button: "right", buttons: 2 });
  await mouse("mouseReleased", rx, ry, { button: "right", buttons: 0 });
  await sleep(200);
  check(await evaluate(`!$("sheet").hidden && state.sheet && state.sheet.id === "${knobPid}" && [...$("sheetBtns").children][1].textContent.includes("✓")`), "right-click opens the attach sheet, CV 2 ticked");
  await evaluate(`[...$("sheetBtns").children][1].click()`);
  await sleep(300);
  check(!(await maps())[0].includes("cv2 " + knobPid) && await evaluate(`$("sheet").hidden`), "sheet: CV 2 taken off again");
  check(errors.length === 0, "no page errors" + (errors.length ? ": " + errors.join(" | ") : ""));
} catch (e) {
  console.log("FAIL exception: " + e.message);
  fails++;
} finally {
  chrome.kill();
}
console.log(fails ? `${fails} failed` : "all passed");
process.exit(fails ? 1 : 0);
