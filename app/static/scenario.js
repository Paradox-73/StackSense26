/* Scenario-file page: a form for every field of the standard input schema (GET /api/scenario/fields), import of a
   scenario JSON (or one element of an array of them), a run through POST /api/scenario, and export of the input and the output as JSON. The loaded file is
   kept as it is (unknown or invalid values included) and only fields the user edits are changed in it. */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const S = { fields: [], doc: { scenario_id: "my_scenario" }, out: null, outFor: null, run: 0, name: "my_scenario" };
const SECTION_NAMES = { project: "Project", scale: "Scale", team: "Team", budget: "Budget", timeline: "Timeline",
  infrastructure: "Infrastructure", requirements: "Requirements", compliance: "Compliance", priorities: "Priorities (1 to 5)" };
const CORE = ["frontend", "backend", "database", "hosting"];
const FX = 96; /* INR per USD: the engine's fixed planning rate (engine/profile.py INR_PER_USD), for the rupee line only */

function getPath(doc, path) {
  let node = doc;
  for (const part of path.split(".")) {
    if (!node || typeof node !== "object" || !(part in node)) return undefined;
    node = node[part];
  }
  return node;
}

function setPath(doc, path, value) {
  const parts = path.split(".");
  let node = doc;
  for (const part of parts.slice(0, -1)) {
    if (!node[part] || typeof node[part] !== "object" || Array.isArray(node[part])) node[part] = {};
    node = node[part];
  }
  const leaf = parts[parts.length - 1];
  if (value === undefined) delete node[leaf]; else node[leaf] = value;
}

async function api(url, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(url, opt);
  if (!r.ok) throw new Error(`the server answered ${r.status}`);
  return r.json();
}

const show = (v) => (v === null || v === undefined ? "" : Array.isArray(v) ? v.join(", ") : String(v));

function control(f) {
  const id = `f-${f.path.replace(/\./g, "-")}`, v = getPath(S.doc, f.path);
  const def = f.default === null || f.default === undefined ? "none" : show(f.default) || "empty";
  const opts = (values, cur) => [`<option value="">(default: ${esc(def)})</option>`]
    .concat(values.map((x) => `<option${String(cur) === String(x) ? " selected" : ""}>${esc(x)}</option>`)).join("");
  if (f.kind === "enum" || f.kind === "priority") return `<select id="${id}" data-path="${f.path}">${opts(f.allowed, v)}</select>`;
  if (f.kind === "bool") return `<select id="${id}" data-path="${f.path}">${opts(["true", "false"], v)}</select>`;
  if (f.kind === "enums") {
    const on = new Set(Array.isArray(v) ? v : []);
    return `<div class="sc-checks" id="${id}" data-path="${f.path}" role="group">${f.allowed.map((x) =>
      `<label><input type="checkbox" value="${esc(x)}"${on.has(x) ? " checked" : ""}>${esc(x)}</label>`).join("")}</div>`;
  }
  if (f.kind === "texts" || f.path === "project.description") {
    const text = Array.isArray(v) ? v.join("\n") : show(v);
    return `<textarea id="${id}" data-path="${f.path}" rows="${f.kind === "texts" ? 2 : 3}">${esc(text)}</textarea>`;
  }
  const num = f.kind !== "text";
  return `<input id="${id}" data-path="${f.path}" type="${num ? "number" : "text"}"${num ? ' inputmode="decimal"' : ""} value="${esc(show(v))}" placeholder="${esc(def)}">`;
}

function renderForm() {
  const groups = {};
  for (const f of S.fields) (groups[f.path.split(".")[0]] = groups[f.path.split(".")[0]] || []).push(f);
  $("#sc-form").innerHTML = Object.entries(groups).map(([sec, list]) => `<fieldset><legend>${esc(SECTION_NAMES[sec] || sec)}</legend>${
    list.map((f) => `<div class="sc-f">${f.kind === "enums" ? `<span class="sc-l">` : `<label for="f-${f.path.replace(/\./g, "-")}">`}<code>${esc(f.path)}</code>${
      f.required ? ' <span class="sc-req" title="required">*</span>' : ""}${f.kind === "enums" ? "</span>" : "</label>"}${control(f)}<span class="sc-h">${esc(f.help)}</span></div>`).join("")
  }</fieldset>`).join("");
}

function readControl(el) {
  const f = S.fields.find((x) => x.path === el.dataset.path);
  if (f.kind === "enums") return [...el.querySelectorAll("input:checked")].map((x) => x.value);
  const raw = el.value.trim();
  /* An emptied list is the empty list and an emptied latency is null (both allowed by the schema); an emptied scalar is
     removed so that it takes its default. */
  if (raw === "") return f.kind === "texts" ? [] : f.kind === "latency" ? null : undefined;
  if (f.kind === "bool") return raw === "true";
  if (f.kind === "texts") return raw.split(f.path === "team.languages" ? /\n|,/ : /\n/).map((x) => x.trim()).filter(Boolean);
  if (f.kind === "text" || f.kind === "enum") return raw;
  const n = Number(raw);
  return Number.isFinite(n) ? n : raw;
}

const codes = (list) => list.map((x) => `<code>${esc(x)}</code>`).join(" ");

function component(layer, c) {
  return `<article class="sc-c"><h3><span class="sc-layer">${esc(layer)}</span>${esc(c.choice)}</h3><p>${esc(c.justification)}</p>
    <p class="small"><span class="muted">Driven by</span> ${codes(c.driven_by)}</p>
    ${c.alternatives.length ? `<div class="sc-k">Alternatives</div><ul>${c.alternatives.map((a) =>
      `<li><b>${esc(a.choice)}</b>: ${esc(a.why_not)}</li>`).join("")}</ul>` : ""}
    ${c.tradeoffs.length ? `<div class="sc-k">Trade-offs</div><ul>${c.tradeoffs.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}</article>`;
}

/* The output can be downloaded only while it belongs to the form as it stands: outFor is the input text it was run on. */
const outCurrent = () => !!S.out && S.outFor === JSON.stringify(S.doc);

function syncOut() {
  $("#sc-dl-out").disabled = !outCurrent();
  if (S.out && !outCurrent()) say("The form changed after this run; run it again to download the output for it.");
}

function renderOut() {
  const o = S.out, box = $("#sc-out");
  syncOut();
  box.removeAttribute("aria-busy");
  if (!o) { box.innerHTML = `<p class="sc-empty">Load a scenario file or pick an example; the result shows here.</p>`; return; }
  const list = (items, fn) => `<ul class="sc-list">${items.map(fn).join("")}</ul>`;
  let h = `<div class="sc-head"><span class="sc-status ${esc(o.status)}">${esc(o.status)}</span>${
    o.architecture_style ? `<span class="sc-style">${esc(o.architecture_style)}</span>` : ""}${
    o.scenario_id !== null ? `<span class="muted small">scenario_id ${esc(o.scenario_id)}, engine ${esc(o.engine_version)}</span>` : ""}</div>
    <p class="sc-sum">${esc(o.summary)}</p>`;
  if (o.validation_errors.length) h += `<h2>Validation errors</h2>${list(o.validation_errors, (e) => `<li><code>${esc(e.field)}</code> ${esc(e.message)}</li>`)}`;
  if (o.warnings.length) h += `<h2>Warnings</h2>${list(o.warnings, (w) =>
    `<li class="sc-w ${esc(w.severity)}"><b>${esc(w.severity)}</b> <code>${esc(w.code)}</code> ${esc(w.message)} ${codes(w.fields)}</li>`)}`;
  if (o.stack) {
    const c = o.estimated_monthly_cost_usd;
    const inr = (v) => `₹${Math.round(v * FX).toLocaleString("en-IN")}`;
    h += `<h2>Stack</h2><p class="sc-cost">Estimated monthly cost: <b>$${c.min.toLocaleString("en-US")} to $${c.max.toLocaleString("en-US")}</b>
      (about ${inr(c.min)} to ${inr(c.max)} at ${FX} INR per USD; an order-of-magnitude band)</p><div class="sc-core">${CORE.map((l) => component(l, o.stack[l])).join("")}</div>
      <h2>Supporting services</h2><div class="sc-sup">${o.stack.supporting.map((s) => component(s.layer, s)).join("")}</div>
      <details><summary>Cost assumptions (${c.assumptions.length})</summary>${list(c.assumptions, (a) => `<li>${esc(a)}</li>`)}</details>`;
  }
  h += `<details${o.stack ? "" : " open"}><summary>Assumptions (${o.assumptions.length})</summary>${list(o.assumptions, (a) => `<li>${esc(a)}</li>`)}</details>`;
  box.innerHTML = h;
}

function download(name, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2) + "\n"], { type: "application/json" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(link);
  link.click();
  link.parentNode.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const say = (t) => { $("#sc-msg").textContent = t; };

/* While a run is in flight: a skeleton in the shape of the result when there is none yet, else the old result dimmed.
   The skeleton never carries .sc-status or .sc-c, which the tests and the screenshot tool wait for. */
const SKELETON = `<div role="status" aria-label="Running the scenario"><div class="sk-lines"><i class="sk" style="--w:38%;height:24px"></i>
  <i class="sk"></i><i class="sk" style="--w:88%"></i><i class="sk" style="--w:62%"></i></div><ul class="sk-stns">${
  "<li><i class=\"sk\"></i><i class=\"sk\"></i><i class=\"sk\"></i></li>".repeat(4)}</ul></div>`;

async function runScenario() {
  const sent = JSON.stringify(S.doc), run = ++S.run, box = $("#sc-out");
  say("Running...");
  if (S.out) box.setAttribute("aria-busy", "true"); else box.innerHTML = SKELETON;
  let out = null, err = null;
  try { out = await api("/api/scenario", S.doc); } catch (e) { err = e; }
  if (run !== S.run) return;  /* a later run or load replaced this one */
  S.out = out; S.outFor = sent;
  say(err ? `Could not run the scenario: ${err.message}.` : `Done: ${out.status}.`);
  renderOut();
}

function load(doc, name) {
  S.doc = doc;  /* kept as loaded, even when it is not an object: the engine then reports invalid_input */
  S.name = String((S.doc && S.doc.scenario_id) ?? name ?? "scenario").replace(/[^A-Za-z0-9_.-]/g, "_");
  S.out = null; S.outFor = null;
  for (const b of document.querySelectorAll("#sc-ex button")) b.setAttribute("aria-pressed", String(b.dataset.name === name));
  renderForm(); renderOut();
  return runScenario();
}

function loadText(text, fileName) {
  let doc;
  try { doc = JSON.parse(text); } catch (e) {
    say(`${fileName} is not valid JSON (${e.message}); nothing was loaded.`);
    return;
  }
  const name = fileName.replace(/\.json$/i, "");
  if (Array.isArray(doc) && doc.length) return offerChoice(doc, name);
  say(`Loaded ${fileName}.`);
  return load(doc, name);
}

/* An array file (such as the organisers' file of all public scenarios): the user picks the element to load. */
function offerChoice(list, name) {
  S.run++; S.out = S.outFor = null; syncOut();  /* a run still in flight must not replace the choice, nor its output stay downloadable */
  const label = (x, i) => {
    const o = x && typeof x === "object" && !Array.isArray(x) ? x : {};
    return `${show(o.scenario_id) || `#${i + 1}`}${o.project && o.project.name ? `: ${show(o.project.name)}` : ""}`;
  };
  say(`${name}.json holds ${list.length} scenarios; pick one.`);
  $("#sc-out").removeAttribute("aria-busy");
  $("#sc-out").innerHTML = `<p class="muted">Which of the ${list.length} scenarios in the file?</p><div class="sc-bar">${
    list.map((x, i) => `<button type="button" class="sc-btn" data-i="${i}">${esc(label(x, i))}</button>`).join("")}</div>`;
  $("#sc-out").onclick = (e) => {
    const b = e.target.closest("button[data-i]");
    if (!b) return;
    $("#sc-out").onclick = null;
    say(`Loaded ${label(list[b.dataset.i], Number(b.dataset.i))} from ${name}.json.`);
    load(list[b.dataset.i], name);
  };
}

async function init() {
  S.fields = await api("/api/scenario/fields");
  const ex = await api("/api/scenario/examples").catch(() => []);
  const group = (g) => ex.filter((x) => x.group === g).map((x) => `<button type="button" data-name="${esc(x.name)}" aria-pressed="false"
    title="${esc(x.project || "")}">${esc(x.name.split("_")[0])}</button>`).join(" ") || "none";
  $("#sc-ex").innerHTML = `${group("public")}<br><span class="muted">Edge cases:</span> ${group("edge")}`;
  renderForm(); renderOut();
  $("#sc-form").addEventListener("change", (e) => {
    const el = e.target.closest("[data-path]");
    if (!el) return;
    if (!S.doc || typeof S.doc !== "object" || Array.isArray(S.doc)) S.doc = {};
    setPath(S.doc, el.dataset.path, readControl(el));
    syncOut();
  });
  $("#sc-ex").addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-name]");
    if (b) load(await api(`/api/scenario/examples/${encodeURIComponent(b.dataset.name)}`), b.dataset.name);
  });
  $("#sc-file").addEventListener("change", async (e) => { const f = e.target.files[0]; e.target.value = ""; if (f) loadText(await f.text(), f.name); });
  $("#sc-run").addEventListener("click", runScenario);
  $("#sc-dl-in").addEventListener("click", () => download(`${S.name}.json`, S.doc));
  $("#sc-dl-out").addEventListener("click", () => outCurrent() && download(`${S.name}_output.json`, S.out));
  let handed = null;  /* a scenario file chosen on the home page's "Load answers" (app.js), read once */
  try { handed = sessionStorage.getItem("ss-scenario"); sessionStorage.removeItem("ss-scenario"); } catch (e) { /* storage blocked */ }
  if (handed) { const f = JSON.parse(handed); return loadText(f.text, f.name); }
  const want = new URLSearchParams(location.search).get("example");
  if (want && ex.some((x) => x.name === want)) load(await api(`/api/scenario/examples/${encodeURIComponent(want)}`), want);
}

init().catch((e) => say(`Could not start: ${e.message}.`));
