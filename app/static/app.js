/* StackSense single-page UI. Vanilla JS, no build step.
   Layout: quick questions (left) -> live result (right, sticky on desktop). Refine = full 32-question form, collapsed.
   Every answer change re-runs the engine (debounced, stale requests aborted). One answer model (S.answers)
   drives the quick chips, the refine form and the what-if sliders, so they always agree.
   "Not sure" marks an answer unknown: the default is used and /api/sensitivity reports which picks depend on it.
   Technical terms carry an (i) popover rendered from data/glossary.json. */
"use strict";

const S = {
  questions: null, presets: [], health: null, glossary: null, answers: {}, result: null,
  reqId: 0, ctl: null, timer: 0, pending: null, panel: null, whyLayer: "frontend",
  growth: null, growthKey: null, growthBusy: null, lastNote: "",
  unknown: new Set(), touched: new Set(), sens: null, sensKey: "", sensCtl: null, sensId: 0,
  briefSrc: {}, summary: null, cause: null, /* where each answer was read from; the last plain-English summary; wording for the next change note */
};
const DEBOUNCE = 250;
const LAYERS = ["frontend", "backend", "database", "hosting"];
const FX = 96; /* the engine's fixed planning rate, INR per USD (FBIL, Sep 2026) */

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n, d = 0) => Number(n).toLocaleString("en-IN", { maximumFractionDigits: d });
const fmtUS = (n, d = 0) => Number(n).toLocaleString("en-US", { maximumFractionDigits: d });
const rng = (lo, hi, f) => (Math.round(lo) === Math.round(hi) ? f(lo) : `${f(lo)}–${f(hi)}`);
const signed = (n, d = 1) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${fmt(Math.abs(n), d)}`;
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
/* Engine sentences use a few shorthand terms; this spells them out in plain words when they are shown. Wording only. */
const PLAIN_TERMS = [
  [/summed lock-in/g, "lock-in scores added up over the four layers (lower is better)"],
  [/summed skill fit/g, "skill-fit scores added up over the four layers"],
  [/summed across layers/g, "added up over the four layers"],
  [/\bstack points, the heaviest answer/g, "stack points (points on the 0-100 stack score), the heaviest answer"],
  [/General quality \(baseline weights\)/g, "General quality (the standard weights every project starts from, before your answers change them)"],
];
const plain = (s) => PLAIN_TERMS.reduce((t, [re, to]) => t.replace(re, to), String(s ?? ""));
const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const smooth = () => (reduced() ? "auto" : "smooth");

function splitLabel(label) {
  const m = /^(.*?)\s*\((.+)\)\s*$/.exec(String(label));
  return m ? [m[1], m[2]] : [String(label), ""];
}
function compact(n) {
  const a = Math.abs(n);
  if (a >= 1e9) return `${fmtUS(n / 1e9, 1)}B`;
  if (a >= 1e6) return `${fmtUS(n / 1e6, 1)}M`;
  if (a >= 1e3) return `${fmtUS(n / 1e3, 1)}k`;
  return fmtUS(n, 0);
}
/** Round to 2 significant digits so slider values read like 1,200 not 1,187. */
function nice(n) {
  if (n <= 0) return 0;
  const p = Math.pow(10, Math.floor(Math.log10(n)) - 1);
  return Math.max(1, Math.round(n / p) * p);
}
const sym = () => (S.answers.currency === "INR" ? "₹" : "$");
const money = (v) => (S.answers.currency === "INR" ? `₹${fmt(v)}` : `$${fmtUS(v)}`);
const usd = (v) => `$${fmtUS(v)}`;
/** Shorten a technology name for tight spaces: "Serverless functions (Node/Python FaaS)" -> "Serverless functions". */
const short = (name) => String(name).replace(/\s*\(.*\)\s*$/, "");

const ICON = {
  arrow: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10M8.5 3.5 13 8l-4.5 4.5"/></svg>',
  down: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.5v8M4.5 7 8 10.5 11.5 7M3 13.5h10"/></svg>',
  print: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 6V2.5h7V6M4.5 11.5h-2v-5h11v5h-2M4.5 9.5h7v4h-7z"/></svg>',
  edit: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10.5 2.5l3 3-8 8h-3v-3z"/></svg>',
  reset: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8a5 5 0 1 0 1.5-3.5M3 2.5v3h3"/></svg>',
  warn: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2 14.5 13.5h-13z M8 6.5v3.2M8 11.6v.1"/></svg>',
  lock: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 7.5h8v6H4zM5.75 7.5V5.25a2.25 2.25 0 0 1 4.5 0V7.5"/></svg>',
  chev: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4"/></svg>',
  info: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.25"/><path d="M8 7.2v4M8 4.9v.1"/></svg>',
  check: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7"/></svg>',
  fork: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 13.5V9M8 9 4 5M8 9l4-4M4 5V2.5M12 5V2.5"/></svg>',
  ext: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M9 3h4v4M13 3 7.5 8.5M11.5 9.5v3.5h-8.5v-8.5h3.5"/></svg>',
  close: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>',
};

async function api(path, body, signal) {
  const opt = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal } : { signal };
  const r = await fetch(path, opt);
  if (!r.ok) throw new Error(`The server answered ${r.status} for ${path}.`);
  return (r.headers.get("content-type") || "").includes("json") ? r.json() : r.text();
}

/* ================================================================== theme: 3-way segmented toggle */
function initTheme() {
  let t = "auto";
  try { t = new URLSearchParams(location.search).get("theme") || localStorage.getItem("ss-theme") || "auto"; } catch (e) { /* storage blocked */ }
  if (!["light", "dark"].includes(t)) t = "auto";
  $$('.theme input[name="theme"]').forEach((r) => {
    r.checked = r.value === t;
    r.onchange = () => {
      if (r.value === "auto") document.documentElement.removeAttribute("data-theme");
      else document.documentElement.setAttribute("data-theme", r.value);
      try { localStorage.setItem("ss-theme", r.value); } catch (e) { /* storage blocked */ }
    };
  });
}

/* ================================================================== questions model */
const allFields = () => S.questions.steps.flatMap((s) => s.fields);
const fieldByKey = (k) => allFields().find((f) => f.key === k);
const stepOfField = (k) => S.questions.steps.findIndex((s) => s.fields.some((f) => f.key === k));
function defaults() {
  const a = {};
  for (const f of allFields()) a[f.key] = structuredClone(f.default);
  return a;
}
const isChanged = (k) => !same(S.answers[k], fieldByKey(k).default);
/** The answers the user (or a preset) actually gave. Untouched and "Not sure" answers are left out, so the
 *  engine applies its defaults and lists them under "Defaults used". */
function sent() {
  const a = {};
  for (const k of S.touched) if (!S.unknown.has(k)) a[k] = structuredClone(S.answers[k]);
  return a;
}

/* ================================================================== quick mode: the 5 questions that matter most */
const APP_SHORT = {
  saas: "SaaS", ecommerce: "E-commerce", realtime_collab: "Realtime / chat", content_site: "Content / SEO site",
  analytics_dashboard: "Dashboards", ml_product: "AI / ML product", iot_telemetry: "IoT", fintech: "Fintech",
  healthcare: "Healthcare", social_network: "Social / UGC", internal_tool: "Internal tool", mobile_first: "Mobile app",
  prototype: "Prototype",
};
/* [value, chip label, upper bound of the bucket the chip stands for] */
const USERS = [[100, "100", 300], [1000, "1k", 3000], [10000, "10k", 30000], [100000, "100k", 300000], [1000000, "1M", 3e6], [10000000, "10M+", Infinity]];
const BUDGET = [[0, "$0", 0], [25, "$25", 50], [100, "$100", 250], [500, "$500", 1000], [2000, "$2k", 5000], [10000, "$10k+", Infinity]];
const TEAM = [[1, "Just me", 1], [3, "2–3", 3], [6, "4–8", 8], [12, "9–20", 20], [40, "20+", Infinity]];
/* rupee budget chips (shown when the currency is INR): [value, label, upper bound of the bucket] */
const BUDGET_INR = [[0, "₹0", 0], [2000, "₹2,000", 5000], [10000, "₹10,000", 25000], [50000, "₹50,000", 120000], [200000, "₹2 lakh", 600000], [1000000, "₹10 lakh+", Infinity]];
const budgetList = () => (S.answers.currency === "INR" ? BUDGET_INR : BUDGET);
const WHERE = [["cloud", "In the cloud"], ["hybrid", "Cloud + our servers"], ["on_prem", "Our own servers"]];
/* must-haves: id -> [chip label, is it on?, turn it on/off in the answers] */
const MUST = [
  ["realtime", "Live updates / chat", (A) => A.realtime === "core", (A, on) => (A.realtime = on ? "core" : "none")],
  ["offline", "Works offline", (A) => !!A.offline, (A, on) => (A.offline = on)],
  ["seo", "Found on Google", (A) => A.seo === "important" || A.seo === "critical", (A, on) => (A.seo = on ? "important" : "none")],
  ["mobile", "iOS / Android app", (A) => (A.platforms || []).some((x) => x === "ios" || x === "android"),
    (A, on) => (A.platforms = on ? [...new Set([...(A.platforms || ["web"]), "ios", "android"])] : ["web"])],
];
const SKILLS = [
  ["js", "JS / TS", ["javascript", "typescript", "react", "node"]], ["python", "Python", ["python"]],
  ["java", "Java", ["java", "spring"]], ["go", "Go", ["go"]], ["csharp", "C# / .NET", ["csharp"]],
  ["php", "PHP", ["php"]], ["any", "No preference", []],
];
const COMP = [["gdpr", "GDPR"], ["dpdp", "India DPDP"], ["hipaa", "HIPAA"], ["pci_dss", "PCI-DSS"], ["soc2", "SOC 2"]];
const JS_KEYS = ["javascript", "typescript", "react", "node", "nextjs"];
const NS = "__ns"; /* value of every "Not sure" chip */
/* quick question id -> the answer(s) it sets; hints come from questions.json */
const QUICK = [
  { id: "app", key: "app_type", title: "What are you building?" },
  { id: "users", key: "dau", title: "Daily users, a year from launch", term: "dau" },
  { id: "budget", key: "budget_monthly", title: "Monthly infrastructure budget", term: "budget" },
  { id: "team", key: "team_size", key2: "team_skills", title: "Team size and strongest language" },
  { id: "comp", key: "compliance", title: "Compliance rules you must meet" },
  { id: "where", key: "deployment", title: "Where must it run?" },
  { id: "must", key: "must", title: "Must-haves (tick any)" },
];
/* Order in which unknown answers are sent to /api/sensitivity (most decisive first): the measured order from
 * tools/question_influence.py (share of re-runs where changing the answer changed a pick), see report/question_influence.md. */
const UNKNOWN_ORDER = ["team_skills", "deployment", "data_shapes", "platforms", "availability", "team_size", "app_type", "existing_systems", "seo", "realtime", "budget_monthly", "cloud_preference", "lock_in_tolerance", "priorities", "dau", "latency_target_ms", "peak_concurrent", "timeline_weeks", "background_work", "tenancy", "peak_rps", "offline", "consistency", "read_write", "compliance", "architecture", "data_volume_gb", "data_growth_gb_month", "user_actions", "special_workloads", "traffic_pattern", "cacheable_share", "regions", "enterprise_sso"];
/* How an answer is named inside a sentence ("Depends on your daily users"). */
const FIELD_NOUN = {
  app_type: "what you are building", dau: "your daily users", budget_monthly: "your budget", team_size: "your team size",
  team_skills: "your team's skills", compliance: "compliance rules", platforms: "your client platforms",
  realtime: "realtime needs", seo: "SEO", consistency: "consistency", availability: "your availability target",
  regions: "where your users are", deployment: "the deployment model", lock_in_tolerance: "lock-in tolerance",
  timeline_weeks: "time to MVP", latency_target_ms: "your latency target", data_shapes: "your data shape",
  read_write: "the read/write mix", data_volume_gb: "data volume", data_growth_gb_month: "data growth",
  architecture: "architecture preference", cloud_preference: "cloud preference", offline: "offline support",
  peak_rps: "peak requests per second", currency: "currency", peak_concurrent: "users online at once",
};
const noun = (k) => FIELD_NOUN[k] || (fieldByKey(k) ? fieldByKey(k).label.toLowerCase() : k);

const budgetUsd = () => (S.answers.currency === "INR" ? (+S.answers.budget_monthly || 0) / FX : +S.answers.budget_monthly || 0);
const bucket = (list, v) => list.find((b) => v <= b[2]);

/** The skill groups (SKILLS ids) that the team_skills answer contains. Empty = no preference. */
function skillGroups() {
  const s = S.answers.team_skills || [];
  return SKILLS.filter((o) => o[2].length && (o[0] === "js" ? o[2].some((x) => s.includes(x)) : s.includes(o[2][0]))).map((o) => o[0]);
}
/** (i) button that opens the glossary popover for one or more terms. */
function infoBtn(terms, label) {
  const ts = [].concat(terms).filter((t) => S.glossary && S.glossary.terms[t]);
  if (!ts.length) return "";
  const name = label || S.glossary.terms[ts[0]].term;
  return `<button type="button" class="gi" data-terms="${esc(ts.join(","))}" aria-haspopup="dialog" aria-expanded="false" aria-label="What is ${esc(name)}?" title="What is ${esc(name)}?">${ICON.info}</button>`;
}
const fieldTerms = (k) => (S.glossary && S.glossary.field_terms[k]) || [];
const optionTerm = (k, v) => (S.glossary && S.glossary.option_terms[k] && S.glossary.option_terms[k][v]) || null;

function chip(name, type, value, label, checked, title, extraCls = "") {
  return `<label class="chip${extraCls ? ` ${extraCls}` : ""}"${title ? ` title="${esc(title)}"` : ""}><input type="${type}" name="${name}" value="${esc(value)}"${checked ? " checked" : ""}><span>${esc(label)}</span></label>`;
}
const nsChip = (name, type = "radio") => chip(name, type, NS, "Not sure", false, "Use the default and show which picks depend on this answer", "ns");
const customChip = (name) => `<label class="chip custom" hidden><input type="radio" name="${name}" value="custom"><span></span></label>`;

function hintBox(id, keys) {
  const txt = keys.map((k) => fieldByKey(k)?.hint).filter(Boolean);
  if (!txt.length) return "";
  return `<button type="button" class="link-btn help-b" data-hint="${id}" aria-expanded="false" aria-controls="hint-${id}">Help me choose</button>
    <div class="hint" id="hint-${id}" hidden>${txt.map((t) => `<p>${esc(t)}</p>`).join("")}</div>`;
}

function renderQuick() {
  const app = fieldByKey("app_type");
  const q = (n, Q, body) => `<fieldset class="q" id="q-${Q.id}"><legend><span class="q-n">${n}</span><span class="q-t">${esc(Q.title)}</span>${Q.term ? infoBtn(Q.term) : ""}<span class="q-ro" id="ro-q-${Q.id}"></span></legend>${body}${hintBox(Q.id, [Q.key, Q.key2].filter(Boolean))}</fieldset>`;
  $("#quick").innerHTML =
    q(1, QUICK[0], `<div class="chips">${app.options.map((o) => chip("q-app", "radio", o.value, APP_SHORT[o.value] || splitLabel(o.label)[0], false, o.label)).join("")}${nsChip("q-app")}</div>`) +
    q(2, QUICK[1], `<div class="chips">${USERS.map(([v, l]) => chip("q-users", "radio", v, l)).join("")}${customChip("q-users")}${nsChip("q-users")}</div>`) +
    q(3, QUICK[2], `<div class="chips">${budgetList().map(([v, l]) => chip("q-budget", "radio", v, l)).join("")}${customChip("q-budget")}${nsChip("q-budget")}</div>`) +
    q(4, QUICK[3], `<div class="chips" role="group" aria-label="Team size">${TEAM.map(([v, l]) => chip("q-team", "radio", v, l)).join("")}${nsChip("q-team")}</div>
      <div class="chips sub" role="group" aria-label="Strongest language">${SKILLS.map(([v, l]) => chip("q-skills", v === "any" ? "radio" : "checkbox", v, l)).join("")}${nsChip("q-skills")}</div>`) +
    q(5, QUICK[4], `<div class="chips">${chip("q-comp", "checkbox", "none", "None")}${COMP.map(([v, l]) => `<span class="chip-g">${chip("q-comp", "checkbox", v, l)}${infoBtn(optionTerm("compliance", v) || v)}</span>`).join("")}${nsChip("q-comp", "checkbox")}</div>`) +
    q(6, QUICK[5], `<div class="chips">${WHERE.map(([v, l]) => chip("q-where", "radio", v, l)).join("")}${nsChip("q-where")}</div>`) +
    q(7, QUICK[6], `<div class="chips">${MUST.map(([v, l]) => chip("q-must", "checkbox", v, l)).join("")}</div>`);
  syncQuick();
}

/** Reflect S.answers (and the unknown set) in the quick chips and their read-outs.
    Point-value chips (users, budget) light up only on an exact match; any other value shows a "Custom" chip. */
function syncQuick() {
  const A = S.answers, U = S.unknown;
  const set = (name, val) => $$(`input[name="${name}"]`).forEach((i) => (i.checked = val !== null && String(i.value) === String(val)));
  const custom = (name, txt) => {
    const c = $(`input[name="${name}"][value="custom"]`)?.closest(".chip");
    if (!c) return;
    c.hidden = !txt;
    if (txt) { $("span", c).textContent = txt; $("input", c).checked = true; }
  };
  set("q-app", U.has("app_type") ? NS : A.app_type);

  const dau = +A.dau || 0, uHit = USERS.find((u) => u[0] === dau);
  set("q-users", U.has("dau") ? NS : uHit ? uHit[0] : null);
  custom("q-users", !U.has("dau") && !uHit ? `Custom: ${compact(dau)}/day` : "");

  const bv = +A.budget_monthly || 0, bHit = budgetList().find((b) => b[0] === bv);
  set("q-budget", U.has("budget_monthly") ? NS : bHit ? bHit[0] : null);
  custom("q-budget", !U.has("budget_monthly") && !bHit ? `Custom: ${sym()}${compact(bv)}/mo` : "");

  /* team chips are ranges ("4–8"), so any size lights up the range it falls in */
  const ts = +A.team_size || 1, tHit = bucket(TEAM, ts);
  set("q-team", U.has("team_size") ? NS : tHit ? tHit[0] : null);
  const sg = skillGroups(), noPref = !(A.team_skills || []).length;
  $$('input[name="q-skills"]').forEach((i) => {
    i.checked = i.value === NS ? U.has("team_skills") : !U.has("team_skills") && (i.value === "any" ? noPref : sg.includes(i.value));
  });
  set("q-where", U.has("deployment") ? NS : A.deployment);
  $$('input[name="q-must"]').forEach((i) => { i.checked = !!MUST.find((m) => m[0] === i.value)[2](A); });

  const comp = A.compliance || [];
  $$('input[name="q-comp"]').forEach((i) => {
    if (i.value === NS) i.checked = U.has("compliance");
    else i.checked = !U.has("compliance") && (i.value === "none" ? comp.length === 0 : comp.includes(i.value));
  });

  const ro = (id, txt) => { const el = $(`#ro-q-${id}`); if (el) el.textContent = txt; };
  const unsure = (k, txt) => (U.has(k) ? `not sure · ${txt}` : txt);
  ro("app", U.has("app_type") ? `not sure · ${APP_SHORT[A.app_type] || A.app_type}` : "");
  ro("users", unsure("dau", `${fmtUS(dau)}/day`));
  ro("budget", unsure("budget_monthly", bv === 0 ? "free tiers only" : `${money(bv)} / month`));
  const sk = A.team_skills || [], pickedSkills = SKILLS.filter((s) => sg.includes(s[0])).flatMap((s) => s[2]);
  const extra = sk.filter((x) => !pickedSkills.includes(x)).length;
  ro("team", unsure("team_size", `${ts} ${ts === 1 ? "person" : "people"}${extra ? ` · +${extra} skills` : ""}`));
  const other = comp.filter((c) => !COMP.some((x) => x[0] === c)).length;
  ro("comp", U.has("compliance") ? "not sure · none" : other ? `+${other} more` : "");
  $$("#quick .q").forEach((fs) => {
    const Q = QUICK.find((x) => `q-${x.id}` === fs.id);
    fs.classList.toggle("unsure", !!Q && (U.has(Q.key) || (Q.key2 && U.has(Q.key2))));
  });
  paintBriefMarks();
}

/* ------------------------------------------------------------------ "Ask me only what matters" (adaptive next questions) */
const LAYER_NAME = { frontend: "Frontend", backend: "Backend", database: "Database", hosting: "Hosting" };
async function askNext() {
  const box = $("#asknext-out"), btn = $("#asknext-btn");
  box.hidden = false; box.innerHTML = `<p class="muted small">Testing the unanswered questions against your answers...</p>`;
  btn.disabled = true;
  try {
    const r = await api("/api/next", { answers: sent() });
    const rows = r.ranked.slice(0, 6).map((x) => `<li><button type="button" class="link-btn" data-edit="${esc(x.key)}">${esc(x.label)}</button>
      <span class="muted small"> can change: ${x.can_change.map((l) => LAYER_NAME[l]).join(", ")}</span></li>`).join("");
    const un = r.settled_questions.length;
    box.innerHTML = `<p class="an-h"><b>${r.settled ? "Settled" : "Provisional"}</b> <span class="muted small">· ${esc(r.note)} (checked with ${r.runs} runs)</span></p>
      ${rows ? `<ol class="an-list">${rows}</ol>` : ""}
      ${un ? `<p class="muted small">${un} other question${un === 1 ? "" : "s"} did not change your stack at the values tested (${Math.min(...r.settled_questions.map((x) => x.tested))}–${Math.max(...r.settled_questions.map((x) => x.tested))} values each, a sample rather than every possible answer).</p>` : ""}`;
  } catch (e) {
    box.innerHTML = `<p class="muted small">Could not check the remaining questions.</p>`;
  } finally { btn.disabled = false; }
}

function onQuickChange(e) {
  const t = e.target, A = S.answers;
  const map = { "q-app": "app_type", "q-users": "dau", "q-budget": "budget_monthly", "q-team": "team_size", "q-skills": "team_skills", "q-comp": "compliance", "q-where": "deployment", "q-must": "must" };
  const key = map[t.name];
  if (!key || t.value === "custom") return;
  if (t.value === NS) {
    if (t.type === "checkbox" && !t.checked) { setUnknown(key, false); return; }
    setUnknown(key, true);
    return;
  }
  const before = structuredClone(A[key]);
  if (key === "app_type") A.app_type = t.value;
  else if (key === "dau") A.dau = +t.value;
  else if (key === "budget_monthly") {
    A.budget_monthly = +t.value;
  } else if (key === "team_size") A.team_size = +t.value;
  else if (key === "team_skills") {
    /* languages add up: ticking a second one keeps the first; "No preference" clears them all */
    if (t.value === "any") A.team_skills = [];
    else {
      const grp = SKILLS.find((s) => s[0] === t.value)[2];
      const cur = S.unknown.has("team_skills") ? [] : [...(A.team_skills || [])];
      A.team_skills = t.checked ? [...new Set([...cur, ...grp])] : cur.filter((x) => !grp.includes(x));
    }
  } else if (key === "deployment") A.deployment = t.value;
  else if (key === "must") {
    const m = MUST.find((x) => x[0] === t.value);
    const keys = { realtime: ["realtime"], offline: ["offline"], seo: ["seo"], mobile: ["platforms"] }[t.value];
    const bef = {}; keys.forEach((k) => (bef[k] = structuredClone(A[k])));
    m[3](A, t.checked);
    commit(keys, bef);
    return;
  }
  else if (key === "compliance") {
    let c = S.unknown.has("compliance") ? [] : [...(A.compliance || [])];
    if (t.value === "none") c = [];
    else if (t.checked) { if (!c.includes(t.value)) c.push(t.value); }
    else c = c.filter((x) => x !== t.value);
    A.compliance = c;
  }
  commit([key], { [key]: before });
}

/* ================================================================== one answer model: every control funnels through here */

/** Mark an answer as "Not sure" (default value + unknown) or clear that mark. */
function setUnknown(k, on) {
  const before = structuredClone(S.answers[k]);
  if (on) { S.unknown.add(k); S.answers[k] = structuredClone(fieldByKey(k).default); }
  else S.unknown.delete(k);
  commit([k], { [k]: before }, { keepUnknown: true });
}

/** After S.answers changed: clear "Not sure" on edited keys, sync every control, schedule a live re-run. */
function commit(keys, before = {}, { keepUnknown = false, skipField = null } = {}) {
  keys.forEach((k) => delete S.briefSrc[k]); /* an answer edited by hand is no longer "read from the description" */
  if (!keepUnknown) keys.forEach((k) => S.unknown.delete(k));
  keys.forEach((k) => (S.unknown.has(k) ? S.touched.delete(k) : S.touched.add(k)));
  syncQuick();
  keys.forEach((k) => { if (k !== skipField) refreshField(k); else markField(k); });
  syncSliders();
  updateCounts();
  queueRun(keys, before);
}

/** Debounced live run. Remembers the first "from" value per key so the change note can say "from X to Y". */
function queueRun(keys, before) {
  const p = S.pending || (S.pending = { from: {} });
  keys.forEach((k) => { if (!(k in p.from)) p.from[k] = k in before ? before[k] : S.answers[k]; });
  setBusy(true);
  clearTimeout(S.timer);
  S.timer = setTimeout(() => {
    const pend = S.pending; S.pending = null;
    const cause = S.cause; S.cause = null;
    run({ change: cause ? { text: cause } : describeChange(pend ? pend.from : {}) });
  }, DEBOUNCE);
}

function valText(k, v) {
  if (v === null || v === undefined || v === "") return k === "peak_rps" ? "derived" : k === "peak_concurrent" ? "not stated" : "blank";
  if (k === "dau") return `${fmtUS(v)} users/day`;
  if (k === "budget_monthly") return `${money(v)}/mo`;
  if (k === "team_size") return `${v} ${+v === 1 ? "person" : "people"}`;
  const f = fieldByKey(k);
  if (!f) return String(v);
  if (f.type === "bool") return v ? "yes" : "no";
  if (f.type === "number") return `${fmtUS(v)}${f.unit ? ` ${f.unit}` : ""}`;
  const lab = (x) => { const o = (f.options || []).find((o) => String(o.value) === String(x)); return o ? splitLabel(o.label)[0] : x; };
  if (Array.isArray(v)) return v.length ? v.map(lab).join(", ") : "none";
  return lab(v);
}

/** A short cause for the gold "what changed" note, e.g. "the budget fell from $50/mo to $10/mo". */
function describeChange(from) {
  const ks = Object.keys(from).filter((k) => !same(from[k], S.answers[k]) || S.unknown.has(k));
  if (ks.length !== 1) return ks.length ? { text: `you changed ${ks.length} answers` } : null;
  const k = ks[0], a = from[k], b = S.answers[k];
  if (S.unknown.has(k)) return { text: `you marked ${noun(k)} as not sure (default ${valText(k, b)} used)` };
  if (["dau", "budget_monthly", "team_size"].includes(k)) {
    const up = +b > +a;
    const verb = { dau: up ? "users rose" : "users fell", budget_monthly: up ? "the budget rose" : "the budget fell", team_size: up ? "the team grew" : "the team shrank" }[k];
    return { text: `${verb} from ${valText(k, a)} to ${valText(k, b)}` };
  }
  return { text: `${noun(k)} changed to ${valText(k, b)}` };
}

/* ================================================================== refine: the full questionnaire */
function defaultText(f) {
  const d = f.default;
  if (d === null || d === undefined) return f.type === "number" ? "derived automatically" : "none";
  if (f.type === "bool") return d ? "Yes" : "No";
  if (f.type === "number") return `${fmtUS(d)}${f.unit ? ` ${f.unit}` : ""}`;
  const lab = (v) => { const o = (f.options || []).find((x) => String(x.value) === String(v)); return o ? splitLabel(o.label)[0] : v; };
  if (Array.isArray(d)) return d.length ? d.map(lab).join(", ") : "none";
  return f.type === "select" ? lab(d) : `"${d}"`;
}

function numReadout(f, v) {
  if (v === null || v === undefined || v === "") return f.key === "peak_rps" ? "Blank: derived from users, app type and peak factor" : f.key === "peak_concurrent" ? "Blank: not stated, changes nothing" : "";
  if (f.key === "budget_monthly") {
    if (+v === 0) return "Free tiers only";
    return S.answers.currency === "INR" ? `₹${fmt(v)} per month ≈ $${fmtUS(v / FX)}` : `$${fmtUS(v)} per month ≈ ₹${fmt(v * FX)}`;
  }
  return Math.abs(v) >= 1000 ? `≈ ${compact(+v)}${f.unit ? ` ${f.unit}` : ""}` : "";
}

function fieldHtml(f) {
  const k = f.key, v = S.answers[k], id = `in-${k}`;
  const group = ["select", "multiselect"].includes(f.type);
  const optInfo = (o) => { const t = optionTerm(k, o.value); return t ? infoBtn(t, splitLabel(o.label)[0]) : ""; };
  const wrapOpt = (o, html) => { const i = optInfo(o); return i ? `<span class="opt-g">${html}${i}</span>` : html; };
  let ctl = "";
  if (f.type === "text") {
    ctl = `<input class="input" type="text" id="${id}" data-k="${k}" value="${esc(v)}" aria-describedby="help-${k}">`;
  } else if (f.type === "number") {
    const prefix = k === "budget_monthly" ? `<span class="affix" data-cur>${sym()}</span>` : "";
    ctl = `<div class="num-wrap">${prefix}<input class="input mono" type="number" inputmode="decimal" step="any" id="${id}" data-k="${k}" value="${v ?? ""}"
        ${f.min != null ? `min="${f.min}"` : ""} ${f.max != null ? `max="${f.max}"` : ""} placeholder="${v == null ? "auto" : ""}" aria-describedby="help-${k} err-${k}">
        ${f.unit ? `<span class="affix unit">${esc(f.unit)}</span>` : ""}</div>
      <p class="readout mono" id="ro-${k}" aria-live="polite">${numReadout(f, v)}</p>
      <p class="field-err" id="err-${k}" hidden></p>`;
  } else if (f.type === "select") {
    ctl = `<div class="opts" role="radiogroup" aria-labelledby="lbl-${k}">${f.options.map((o) => {
      const [m, sub] = splitLabel(o.label);
      return wrapOpt(o, `<label class="opt"><input type="radio" name="${k}" value="${esc(o.value)}" data-k="${k}" ${String(o.value) === String(v) ? "checked" : ""}>
        <span class="o-main">${esc(m)}</span>${sub ? `<span class="o-sub">${esc(sub)}</span>` : ""}</label>`);
    }).join("")}</div>`;
  } else if (f.type === "multiselect") {
    const sel = v || [];
    const extra = sel.filter((x) => !f.options.some((o) => o.value === x)).map((x) => ({ value: x, label: x }));
    ctl = `<div class="opts multi" role="group" aria-labelledby="lbl-${k}">${f.options.concat(extra).map((o) => {
      const [m, sub] = splitLabel(o.label);
      return wrapOpt(o, `<label class="opt"><input type="checkbox" value="${esc(o.value)}" data-k="${k}" ${sel.includes(o.value) ? "checked" : ""}>
        <span class="o-main">${esc(m)}</span>${sub && f.options.length <= 10 ? `<span class="o-sub">${esc(sub)}</span>` : ""}${k === "data_shapes" || k === "priorities" ? `<span class="ord mono" data-ord="${esc(k)}:${esc(o.value)}"></span>` : ""}</label>`);
    }).join("")}</div>
    ${f.free ? `<label class="sr-only" for="free-${k}">Add a skill that is not listed</label>
      <input class="input free" id="free-${k}" data-free="${k}" type="text" placeholder="Another skill? Type it and press Enter">` : ""}`;
  } else if (f.type === "bool") {
    ctl = `<label class="switch"><input type="checkbox" role="switch" id="${id}" data-k="${k}" ${v ? "checked" : ""}><span class="track" aria-hidden="true"></span><span class="sw-txt">${v ? "Yes" : "No"}</span></label>`;
  }
  const src = (f.sources || []).map((s) => `<li><a href="${esc(s)}" target="_blank" rel="noopener">${esc(s.replace(/^https?:\/\/(www\.)?/, ""))}</a></li>`).join("");
  const labelTag = group ? `<span class="f-label" id="lbl-${k}">` : `<label class="f-label" id="lbl-${k}" for="${id}">`;
  const optTerms = new Set(Object.values((S.glossary && S.glossary.option_terms[k]) || {}));
  const fTerms = fieldTerms(k).filter((t) => !optTerms.has(t));
  const unsure = S.unknown.has(k), canNs = k !== "project_name" && k !== "currency";
  return `<div class="field${isChanged(k) ? " changed" : ""}${unsure ? " unsure" : ""}" id="f-${k}" data-field="${k}">
    <div class="f-title">${labelTag}${esc(f.label)}${group ? "</span>" : "</label>"}${fTerms.length ? infoBtn(fTerms, f.label) : ""}<span class="chg-dot" title="Edited"></span>
      ${canNs ? `<label class="ns-t" title="Use the default and show which picks depend on this answer"><input type="checkbox" data-ns="${k}" ${unsure ? "checked" : ""}><span>Not sure</span></label>` : ""}</div>
    <p class="f-help" id="help-${k}">${esc(f.help || "")}</p>
    <div class="f-ctl">${ctl}</div>
    <p class="f-meta">Default: <span class="mono">${esc(defaultText(f))}</span>
      <button type="button" class="link-btn reset-one" data-reset="${k}">${ICON.reset}Use default</button>
      ${f.hint ? `<button type="button" class="link-btn" data-fhint="${k}" aria-expanded="false" aria-controls="fh-${k}">Help me choose</button>` : ""}
      ${f.why ? `<button type="button" class="link-btn" data-why="${k}" aria-expanded="false" aria-controls="why-${k}">Why we ask</button>` : ""}</p>
    ${f.hint ? `<div class="hint" id="fh-${k}" hidden><p>${esc(f.hint)}</p></div>` : ""}
    ${f.why ? `<div class="why" id="why-${k}" hidden><p>${esc(f.why)}</p>${src ? `<ul class="src">${src}</ul>` : ""}</div>` : ""}
  </div>`;
}

function renderRefine() {
  const openSet = new Set($$("#form details[open]").map((d) => d.dataset.step));
  $("#form").innerHTML = S.questions.steps.map((st, i) => {
    const n = st.fields.filter((f) => isChanged(f.key)).length;
    return `<details class="grp" data-step="${i}"${openSet.has(String(i)) ? " open" : ""}>
      <summary><span class="g-t">${esc(st.title)}</span><span class="g-c" id="gc-${i}">${st.fields.length} questions${n ? ` · <b>${n} edited</b>` : ""}</span>${ICON.chev}</summary>
      <p class="g-sub">${esc(st.subtitle)}</p>${st.fields.map(fieldHtml).join("")}</details>`;
  }).join("");
  updateOrd(); updateCounts();
}

function updateCounts() {
  if (!S.questions) return;
  let total = 0;
  S.questions.steps.forEach((st, i) => {
    const n = st.fields.filter((f) => isChanged(f.key)).length; total += n;
    const u = st.fields.filter((f) => S.unknown.has(f.key)).length;
    const el = $(`#gc-${i}`); if (el) el.innerHTML = `${st.fields.length} questions${n ? ` · <b>${n} edited</b>` : ""}${u ? ` · <i>${u} not sure</i>` : ""}`;
  });
  const u = S.unknown.size;
  $("#refine-count").textContent = [total ? `${total} answers differ from defaults` : "optional · every one has a default", u ? `${u} marked not sure` : ""].filter(Boolean).join(" · ");
}

function updateOrd() {
  $$("[data-ord]").forEach((el) => {
    const [fk, val] = el.dataset.ord.split(":");
    const i = (S.answers[fk] || []).indexOf(val);
    el.textContent = i < 0 ? "" : i === 0 && fk === "data_shapes" ? "primary" : `#${i + 1}`;
  });
}

/** Side effects of a value change that live outside the field itself. */
function fieldSideEffects(k) {
  if (k === "data_shapes" || k === "priorities") updateOrd();
  if (k === "currency") {
    $$("[data-cur]").forEach((x) => (x.textContent = sym()));
    renderQuick();
    const ro = $("#ro-budget_monthly"); if (ro) ro.textContent = numReadout(fieldByKey("budget_monthly"), S.answers.budget_monthly);
    renderWhatIf(true);
  }
}

/** Update a field's edited / not-sure marks without re-drawing it (used while the user is typing in it). */
function markField(k) {
  const el = $(`#f-${k}`);
  if (el) {
    el.classList.toggle("changed", isChanged(k));
    el.classList.toggle("unsure", S.unknown.has(k));
    const ns = $(`[data-ns="${k}"]`, el); if (ns) ns.checked = S.unknown.has(k);
  }
  fieldSideEffects(k);
}

/** Re-draw one refine field after its value changed elsewhere (quick chips, sliders, "Pick this"). */
function refreshField(k, focusSel) {
  const el = $(`#f-${k}`);
  if (el) {
    const whyOpen = !$(".why", el)?.hidden, hintOpen = !$(".hint", el)?.hidden;
    el.outerHTML = fieldHtml(fieldByKey(k));
    if (whyOpen && $(`#why-${k}`)) { $(`#why-${k}`).hidden = false; $(`[data-why="${k}"]`).setAttribute("aria-expanded", "true"); }
    if (hintOpen && $(`#fh-${k}`)) { $(`#fh-${k}`).hidden = false; $(`[data-fhint="${k}"]`).setAttribute("aria-expanded", "true"); }
    if (focusSel) $(focusSel)?.focus();
  }
  fieldSideEffects(k);
}

function bindRefine() {
  const form = $("#form");
  form.addEventListener("input", (e) => {
    const t = e.target, k = t.dataset.k;
    if (!k) return;
    const f = fieldByKey(k), before = structuredClone(S.answers[k]);
    if (f.type === "number") {
      const raw = t.value.trim();
      S.answers[k] = raw === "" ? null : Number(raw);
      const err = $(`#err-${k}`), v = S.answers[k];
      let msg = "";
      if (v !== null && Number.isFinite(v)) {
        if (f.min != null && v < f.min) msg = `Below the minimum of ${fmtUS(f.min)}; the engine will raise it and add a warning.`;
        else if (f.max != null && v > f.max) msg = `Above the maximum of ${fmtUS(f.max)}; the engine will cap it and add a warning.`;
      }
      err.hidden = !msg; err.textContent = msg;
      t.setAttribute("aria-invalid", msg ? "true" : "false");
      $(`#ro-${k}`).textContent = numReadout(f, v);
    } else if (f.type === "text") S.answers[k] = t.value;
    else return;
    commit([k], { [k]: before }, { skipField: k });
  });
  form.addEventListener("change", (e) => {
    const t = e.target;
    if (t.dataset.ns) {
      const k = t.dataset.ns;
      setUnknown(k, t.checked);
      $(`#f-${k} [data-ns]`)?.focus();
      return;
    }
    const k = t.dataset.k;
    if (!k) return;
    const f = fieldByKey(k), before = structuredClone(S.answers[k]);
    if (f.type === "select") S.answers[k] = t.value;
    else if (f.type === "bool") { S.answers[k] = t.checked; $(".sw-txt", t.parentElement).textContent = t.checked ? "Yes" : "No"; }
    else if (f.type === "multiselect") {
      const arr = S.unknown.has(k) ? [] : [...(S.answers[k] || [])], i = arr.indexOf(t.value);
      if (t.checked && i < 0) arr.push(t.value);
      if (!t.checked && i >= 0) arr.splice(i, 1);
      S.answers[k] = arr;
      if (S.unknown.has(k)) { S.unknown.delete(k); commit([k], { [k]: before }); return; }
    } else return;
    commit([k], { [k]: before }, { skipField: k });
  });
  form.addEventListener("keydown", (e) => {
    const t = e.target;
    if (t.dataset && t.dataset.free && e.key === "Enter") {
      e.preventDefault();
      const k = t.dataset.free, val = t.value.trim().toLowerCase();
      if (!val) return;
      const before = structuredClone(S.answers[k]);
      const arr = [...(S.answers[k] || [])];
      if (!arr.includes(val)) arr.push(val);
      S.answers[k] = arr;
      commit([k], { [k]: before });
      $(`#free-${k}`)?.focus();
    } else if (e.key === "Enter" && t.tagName === "INPUT" && t.type !== "checkbox" && t.type !== "radio") e.preventDefault();
  });
  form.addEventListener("click", (e) => {
    const r = e.target.closest("[data-reset]");
    if (r) {
      const k = r.dataset.reset, before = structuredClone(S.answers[k]);
      S.answers[k] = structuredClone(fieldByKey(k).default);
      commit([k], { [k]: before });
      S.touched.delete(k);
      $(`#f-${k} [data-reset]`)?.focus();
      return;
    }
    const w = e.target.closest("[data-why]");
    if (w) {
      const box = $(`#why-${w.dataset.why}`), open = box.hidden;
      box.hidden = !open; w.setAttribute("aria-expanded", String(open));
      return;
    }
    const h = e.target.closest("[data-fhint]");
    if (h) {
      const box = $(`#fh-${h.dataset.fhint}`), open = box.hidden;
      box.hidden = !open; h.setAttribute("aria-expanded", String(open));
    }
  });
}

function toggleRefine(open) {
  const btn = $("#refine-toggle"), box = $("#refine");
  const willOpen = open ?? box.hidden;
  box.hidden = !willOpen;
  btn.setAttribute("aria-expanded", String(willOpen));
  if (willOpen && !$("#form").innerHTML) renderRefine();
}

/* ================================================================== examples */
function renderExamples() {
  $("#examples").innerHTML = S.presets.map((p) => {
    const name = p.name.replace(/^Edge case:\s*/i, "");
    return `<button type="button" class="ex" data-preset="${esc(p.id)}" title="${esc(p.description)}">${esc(cap(name))}</button>`;
  }).join("") + `<button type="button" class="ex more" id="ex-more" aria-expanded="false">More examples</button>`;
  $("#examples").onclick = (e) => {
    if (e.target.closest("#ex-more")) {
      const w = $("#examples-wrap"); w.classList.toggle("all");
      e.target.closest("#ex-more").setAttribute("aria-expanded", String(w.classList.contains("all")));
      return;
    }
    const b = e.target.closest("[data-preset]");
    if (b) runPreset(b.dataset.preset);
  };
}

/** Replace every answer with `input` (a project from a preset, a link or a file); `unknown` are marked "Not sure". */
function loadProject(input, unknown = [], presetId = null) {
  clearTimeout(S.timer); S.pending = null; S.briefSrc = {};
  S.answers = Object.assign(defaults(), structuredClone(input));
  S.unknown.clear();
  /* Every answer the project states is sent, even one equal to this page's default: the engine's
   * default for some questions depends on other answers (the app type), so leaving it out could change it. */
  S.touched = new Set(Object.keys(input).filter((k) => fieldByKey(k)));
  for (const k of unknown) { S.unknown.add(k); S.answers[k] = structuredClone(fieldByKey(k).default); S.touched.delete(k); }
  syncQuick(); syncSliders();
  if ($("#form").innerHTML) renderRefine();
  updateCounts();
  $$("#examples .ex").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.preset === presetId)));
  return run({ compare: false });
}

function runPreset(id) {
  const p = S.presets.find((x) => x.id === id);
  return p ? loadProject(p.input, [], id) : Promise.resolve();
}

/** The address that reopens the current answers: only the answers given and the "Not sure" ones. */
const shareUrl = () => `${location.origin}${location.pathname}#a=${Share.encode(sent(), S.unknown)}`;

/* ================================================================== run the engine (live) */

/** Show or hide the subtle "updating" state on the result and the mobile summary bar. */
function setBusy(on) {
  $("#out").classList.toggle("busy", on);
  $("#sumbar")?.classList.toggle("busy", on);
}

/**
 * Re-run /api/recommend for the current answers. A newer call aborts the older fetch (AbortController),
 * and a response that arrives after a newer request was sent is ignored (request id check).
 * compare=false (presets, first load) renders without "was X" highlights.
 */
async function run({ change = null, compare = true } = {}) {
  const id = ++S.reqId, out = $("#out"), prev = S.result;
  if (S.ctl) S.ctl.abort();
  const ctl = (S.ctl = new AbortController());
  if (!prev) out.innerHTML = skeleton();
  setBusy(true);
  try {
    const r = await api("/api/recommend", sent(), ctl.signal);
    if (id !== S.reqId) return; /* a newer request superseded this one */
    S.result = r;
    if (!compare) S.lastNote = "";
    renderResults(compare ? prev : null, change);
    loadSensitivity();
  } catch (e) {
    if (e.name === "AbortError" || id !== S.reqId) return;
    if (!S.result) out.innerHTML = `<div class="empty" role="alert"><h2>Could not get a recommendation</h2><p>${esc(e.message)} Check that the StackSense server is running (<code>python run.py</code>), then change any answer to retry.</p></div>`;
    else { const el = $("#run-error"); if (el) { el.textContent = `${e.message} Showing the previous result.`; el.hidden = false; } }
  } finally {
    if (id === S.reqId) { setBusy(false); S.ctl = null; }
  }
}

function skeleton() {
  return `<div class="skel" aria-busy="true" aria-label="Scoring every technology and stack combination">
    <div class="sk sk-head"></div><div class="sk-grid">${LAYERS.map(() => '<div class="sk sk-card"></div>').join("")}</div><div class="sk sk-bar"></div></div>`;
}

/* ================================================================== result: small parts */
const confWord = { high: "clear winner", medium: "solid lead", low: "close call" };

/** "Cost at your scale: 5.0/5 vs 2.8 average for this layer - weighted up because: Modest budget; X." -> parts */
function parseWhy(line) {
  const m = /^(.+?): ([\d.]+)\/5 vs ([\d.]+) average for this layer(?: - weighted up because: (.+?))?\.?$/.exec(line || "");
  if (!m) return null;
  return { crit: m[1], a: m[2], b: m[3], because: m[4] ? m[4].split(";")[0].trim() : "" };
}
function oneLine(s) {
  const p = parseWhy(s.explanation.why[0]);
  if (!p) return esc(s.explanation.why[0] || s.pick.summary);
  return `<b>${esc(p.crit)}</b> ${esc(p.a)}/5 vs ${esc(p.b)} avg${p.because ? ` · ${esc(p.because)}` : ""}`;
}

function dial(score) {
  const r = 27, C = 2 * Math.PI * r, p = Math.max(0, Math.min(100, score)) / 100;
  return `<svg class="dial" viewBox="0 0 64 64" role="img" aria-label="Stack fit score ${score.toFixed(1)} out of 100">
    <circle cx="32" cy="32" r="${r}" class="d-track"/>
    <circle cx="32" cy="32" r="${r}" class="d-val" stroke-dasharray="${(C * p).toFixed(1)} ${C.toFixed(1)}" transform="rotate(-90 32 32)"/>
    <text x="32" y="37" class="d-num" id="score-num">${score.toFixed(1)}</text></svg>`;
}

function divChart(rows) {
  if (!rows.length) return `<p class="muted">No single answer moved this score by more than 0.05 points.</p>`;
  const m = Math.max(0.01, ...rows.map((r) => Math.abs(r.value)));
  return `<div class="dchart" role="list">${rows.map((r) => {
    const w = (Math.abs(r.value) / m) * 100;
    return `<div class="d-row" role="listitem"><span class="d-lab">${esc(r.label)}</span>
      <span class="d-track"><span class="d-neg">${r.value < 0 ? `<i style="--w:${w.toFixed(1)}%"></i>` : ""}</span><span class="d-pos">${r.value > 0 ? `<i style="--w:${w.toFixed(1)}%"></i>` : ""}</span></span>
      <span class="d-num mono ${r.value < 0 ? "neg" : "pos"}">${signed(r.value, 1)}</span></div>`;
  }).join("")}</div>`;
}

function hbars(rows, max, d = 1) {
  return `<div class="hbars">${rows.map((r) => `<div class="h-row${r.hl ? " hl" : ""}"><span class="h-lab">${r.html ?? esc(r.label)}</span>
    <span class="h-track"><i style="--w:${Math.max(0, Math.min(100, (r.value / max) * 100)).toFixed(1)}%"></i></span>
    <span class="h-num mono">${fmt(r.value, d)}</span></div>`).join("")}</div>`;
}
const list = (arr, cls = "") => (arr && arr.length ? `<ul class="${cls}">${arr.map((x) => `<li>${esc(plain(x))}</li>`).join("")}</ul>` : `<p class="muted">None.</p>`);
const link = (s) => `<a href="${esc(s)}" target="_blank" rel="noopener">${esc(s.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, ""))}</a>`;

/* ================================================================== result: page */
const PANELS = [
  ["why", "Why these picks"], ["growth", "Growth path"], ["arch", "Architecture"],
  ["cost", "Cost"], ["alts", "Alternatives"], ["inputs", "Inputs & weights"],
];

function renderResults(prev, change) {
  const out = $("#out"), r = S.result;
  if (!$("#res", out)) {
    out.innerHTML = `<div class="res" id="res">
      <p class="upd" id="upd" aria-hidden="true"><i></i>Updating…</p>
      <div id="res-head"></div><div id="res-warn"></div><ol class="picks" id="picks"></ol>
      <p class="run-error" id="run-error" role="alert" hidden></p>
      <div id="summary"></div>
      <div id="second"></div>
      <div id="depends"></div>
      <p class="trace"><span>${ICON.lock} Same answers → same stack. Scores follow a published 1–5 rubric.</span>
        <button type="button" class="link-btn" data-open="why">Show the trace</button></p>
      <div id="whatif"></div>
      <div id="whatif-q"></div>
      <div class="drawers" role="group" aria-label="Details">${PANELS.map(([id, l]) => `<button type="button" class="drawer-b" data-open="${id}" aria-expanded="false" aria-controls="panel-${id}">${l}</button>`).join("")}</div>
      <div class="panels">${PANELS.map(([id, l]) => `<section class="panel" id="panel-${id}" data-title="${esc(l)}" aria-label="${esc(l)}" hidden></section>`).join("")}</div>
      <div class="exports"><span>Export</span>
        <button class="link-btn" type="button" id="exp-json">${ICON.down}JSON</button>
        <button class="link-btn" type="button" id="exp-md">${ICON.down}Markdown</button>
        <button class="link-btn" type="button" id="exp-adr" title="One architecture decision record per layer">${ICON.down}Decision records</button>
        <button class="link-btn" type="button" id="do-print">${ICON.print}Print / PDF</button>
        <span class="exp-sep">Share</span>
        <button class="link-btn" type="button" id="share-copy" title="Copy a link that reopens these answers">Copy link</button>
        <button class="link-btn" type="button" id="share-save" title="Download your answers as a small JSON file">${ICON.down}Answers (JSON)</button>
        <button class="link-btn" type="button" id="share-load" title="Load answers from a JSON file">Load answers</button>
        <input type="file" id="share-file" accept="application/json,.json" hidden>
        <span id="share-note" role="status" aria-live="polite"></span></div>
    </div>`;
    bindExports();
  }
  $("#run-error").hidden = true;
  renderHead(prev);
  renderWarnings();
  renderPicks(prev, change);
  renderDepends();
  renderSummary();
  renderSecond();
  renderWhatIf();
  renderWhatIfText();
  S.growth = null;
  renderPanels();
  if (S.panel) openPanel(S.panel, { keep: true });
  renderSummaryBar(prev);
  stickyOffset();
}

function renderHead(prev) {
  const r = S.result, pr = r.profile || {}, d = r.derived || {};
  const name = pr.project_name && pr.project_name !== "My project" ? pr.project_name : "Your stack";
  if (!r.feasible) {
    $("#res-head").innerHTML = `<header class="rh"><div class="rh-t"><p class="kicker">No feasible stack</p><h2 id="res-title" tabindex="-1">${esc(name)}</h2></div></header>`;
    return;
  }
  const c = r.cost;
  const status = { within: "within budget", stretch: "stretches the budget", over: "over budget" }[c.status] || c.status;
  const inr = pr.currency === "INR";
  $("#res-head").innerHTML = `<header class="rh">
    <div class="rh-score">${dial(r.stack_score)}<span>fit score</span></div>
    <div class="rh-t"><p class="kicker">${esc(r.architecture.style)} · ${esc(d.tier_label || "")}</p>
      <h2 id="res-title" tabindex="-1">${esc(name)}</h2></div>
    <div class="rh-cost"><span class="k">Monthly cost</span>
      <b class="mono" id="cost-num">${costText(r)}</b>
      <span class="st st-${esc(c.status)}">${esc(status)} · ${inr ? `₹${fmt(pr.budget_monthly)}` : usd(c.budget_usd)}</span></div>
  </header>`;
  if (prev && prev.feasible && !reduced()) tween($("#score-num"), prev.stack_score, r.stack_score);
}
const costText = (r) => {
  const c = r.cost;
  return (r.profile || {}).currency === "INR" ? rng(c.total_low_inr ?? c.total_low * FX, c.total_high_inr ?? c.total_high * FX, (v) => `₹${fmt(v)}`) : rng(c.total_low, c.total_high, usd);
};

function tween(el, a, b) {
  if (!el || a === b) return;
  const t0 = performance.now(), dur = 450;
  const step = (t) => {
    const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = (a + (b - a) * e).toFixed(1);
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function renderWarnings() {
  const ws = S.result.warnings || [], el = $("#res-warn");
  if (!ws.length) { el.innerHTML = ""; return; }
  const wasOpen = !!$("details[open]", el);
  const order = { critical: 0, warning: 1, info: 2 };
  const sorted = [...ws].sort((a, b) => (order[a.severity] ?? 3) - (order[b.severity] ?? 3));
  const crit = ws.filter((w) => w.severity === "critical").length;
  el.innerHTML = `<details class="wbanner${crit ? " crit" : ""}"${wasOpen ? " open" : ""}>
    <summary>${ICON.warn}<span><b>${ws.length} input ${ws.length === 1 ? "conflict" : "conflicts"} resolved</b> · ${esc(sorted[0].title)}${ws.length > 1 ? ` and ${ws.length - 1} more` : ""}</span><span class="wb-more">Details</span></summary>
    <ol class="wlist">${sorted.map((w) => `<li class="sev-${esc(w.severity)}">
      <p class="w-t"><span class="sev">${esc(w.severity)}</span><b>${esc(w.title)}</b></p>
      <p>${esc(w.detail)}</p><p class="w-res"><b>Resolved:</b> ${esc(w.resolution)}</p>
      ${(w.fields || []).filter(fieldByKey).length ? `<p class="w-fields">${w.fields.filter(fieldByKey).map((k) => `<button type="button" class="link-btn" data-edit="${esc(k)}">${ICON.edit}Edit “${esc(fieldByKey(k).label)}”</button>`).join("")}</p>` : ""}
    </li>`).join("")}</ol></details>`;
}

/** The four cards. Only cards whose pick changed since the previous run animate (gold + "was X"). */
function renderPicks(prev, change) {
  const r = S.result, el = $("#picks");
  if (!r.feasible) {
    el.innerHTML = `<li class="infeasible"><h3>No stack meets all your requirements</h3><p>The conflicts above name the answers that rule out every option in a layer. Relax one, or move a slider below.</p></li>`;
    return;
  }
  const first = !el.children.length || !!$(".infeasible", el);
  const notes = [];
  el.innerHTML = LAYERS.map((l, i) => {
    const s = r.stack[l], was = prev && prev.feasible ? prev.stack[l].pick.name : null;
    const changed = was && was !== s.pick.name;
    if (changed) notes.push({ layer: l, from: was, to: s.pick.name, s });
    return `<li class="pick${first ? " enter" : ""}${changed ? " changed" : ""}" style="--i:${i}" data-layer="${l}">
      <button type="button" class="pick-b" data-open="why" data-layer="${l}" aria-label="${esc(cap(l))}: ${esc(s.pick.name)}${changed ? `, changed from ${esc(was)}` : ""}, fit ${s.pick.score.toFixed(0)} of 100. Show reasoning">
        <span class="p-l">${esc(s.title)}</span><span class="p-s mono">${s.pick.score.toFixed(0)}</span>
        <span class="p-n">${esc(short(s.pick.name))}${s.api_host ? ` <small>+ API on ${esc(short(s.api_host.name))}</small>` : ""}</span>
        ${changed ? `<span class="p-was">was ${esc(short(was))}</span>` : ""}
        <span class="p-r">${oneLine(s)}</span>
        <span class="p-dep" data-dep="${l}" hidden></span>
      </button></li>`;
  }).join("");
  if (prev) setNote(notes, prev, change);
}

/** The gold "what changed and why" line under the sliders. */
function setNote(notes, prev, change) {
  const r = S.result;
  const cause = change ? change.text : "you changed your answers";
  let html;
  if (notes.length) {
    html = notes.map((n) => `<li><b>${esc(cap(n.layer))} switched:</b> <s>${esc(short(n.from))}</s> → <b class="g">${esc(short(n.to))}</b> after ${esc(cause)}.<span class="sw-why" data-sw="${n.layer}"></span></li>`).join("");
    loadSwitchReasons(prev, r);
  } else if (prev.feasible && r.feasible) {
    const cp = rng(prev.cost.total_low, prev.cost.total_high, usd), cn = rng(r.cost.total_low, r.cost.total_high, usd);
    html = `<li>No layer changed after ${esc(cause)}. Score ${prev.stack_score.toFixed(1)} → ${r.stack_score.toFixed(1)}${cp !== cn ? `, cost ${cp} → ${cn}` : ""}.</li>`;
  } else html = `<li>Re-ran after ${esc(cause)}.</li>`;
  S.lastNote = html;
  const el = $("#wi-note");
  if (el) { el.innerHTML = html; el.classList.toggle("hit", notes.length > 0); }
}

/** Ask the engine what actually caused each switch (an exclusion, the criterion or penalty that moved the gap, or a stack rule). */
async function loadSwitchReasons(prev, r) {
  try {
    const sw = await api("/api/switch", { before: prev.profile, after: r.profile });
    if (S.result !== r) return;
    Object.entries(sw).forEach(([l, x]) => { const el = $(`[data-sw="${l}"]`); if (el && x.why) el.textContent = ` ${x.why}`; });
    const box = $("#wi-note");
    if (box) S.lastNote = box.innerHTML;
  } catch (e) { /* the note still says what changed; the cause is extra */ }
}

/* ------------------------------------------------------------------ "Not sure" -> Depends on */
const sensKey = () => JSON.stringify([S.answers, unknownList()]);
const unknownList = () => [...S.unknown].sort((a, b) => {
  const ia = UNKNOWN_ORDER.indexOf(a), ib = UNKNOWN_ORDER.indexOf(b);
  return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || allFields().findIndex((f) => f.key === a) - allFields().findIndex((f) => f.key === b);
});

async function loadSensitivity() {
  const unknown = unknownList(), key = sensKey();
  if (S.sensCtl) { S.sensCtl.abort(); S.sensCtl = null; }
  if (!unknown.length) { S.sens = null; S.sensKey = ""; renderDepends(); return; }
  if (S.sens && S.sensKey === key) { renderDepends(); return; }
  const ctl = (S.sensCtl = new AbortController()), id = ++S.sensId;
  renderDepends(); /* the previous answer stays visible, dimmed, until the new one arrives */
  try {
    const r = await api("/api/sensitivity", { answers: sent(), unknown }, ctl.signal);
    if (id !== S.sensId) return;
    S.sens = r; S.sensKey = key;
    renderDepends();
  } catch (e) {
    if (e.name === "AbortError" || id !== S.sensId) return;
    $("#depends").innerHTML = `<div class="dep"><p class="muted small" role="alert">Could not check which picks depend on your unknown answers: ${esc(e.message)}</p></div>`;
  } finally {
    if (id === S.sensId) S.sensCtl = null;
  }
}

/** Short value text for a tested option, e.g. "10k/day", "$500/mo", "6 people". */
function optText(k, v, label) {
  if (k === "dau") return `${compact(v)}/day`;
  if (k === "budget_monthly") return +v === 0 ? `${sym()}0` : `${sym()}${compact(v)}/mo`;
  if (k === "team_size") return `${v} ${+v === 1 ? "person" : "people"}`;
  if (k === "peak_rps") return v == null ? "derived" : `${compact(v)} req/s`;
  if (k === "peak_concurrent") return v == null ? "not stated" : `${compact(v)} online`;
  if (fieldByKey(k)?.type === "number") return `${compact(v)} ${fieldByKey(k).unit || ""}`.trim();
  return splitLabel(label)[0];
}

function renderDepends() {
  const box = $("#depends");
  if (!box || !S.result) return;
  $$("[data-dep]").forEach((x) => { x.hidden = true; x.textContent = ""; });
  const unknown = unknownList();
  if (!unknown.length) {
    box.innerHTML = `<p class="dep-tip">${ICON.fork}<span>Unsure about an answer? Choose <b>Not sure</b> on any question and StackSense shows which picks depend on it.</span></p>`;
    return;
  }
  const names = unknown.map(noun);
  if (!S.sens) {
    box.innerHTML = `<div class="dep loading" aria-busy="true"><p class="dep-h"><b>Checking what depends on your ${unknown.length === 1 ? "unknown answer" : `${unknown.length} unknown answers`}</b> <span class="muted">(${esc(names.join(", "))})…</span></p></div>`;
    return;
  }
  const s = S.sens;
  if (!s.feasible) { box.innerHTML = `<div class="dep"><p class="muted small">No feasible stack at the default values, so sensitivity was not computed.</p></div>`; return; }
  const robust = s.robust_layers.map(cap), tags = {};
  const blocks = s.fields.filter((f) => f.matters.length).map((f) => {
    const lines = f.matters.map((l) => {
      const L = f.layers[l], base = s.base[l];
      let txt, alts;
      if (f.ordered) {
        const segs = L.segments, n = segs.length;
        txt = segs.map((g, i) => {
          const a = optText(f.key, g.from, g.from_label), b = optText(f.key, g.to, g.to_label);
          const where = i === 0 ? `up to ${b}` : i === n - 1 ? `from ${a}` : a === b ? `at ${a}` : `${a}–${b}`;
          return `<b>${esc(short(g.pick || "no option"))}</b> ${esc(where)}`;
        }).join(", ");
        alts = segs.filter((g) => g.pick_id && g.pick !== base).map((g) => ({ pick: g.pick, value: g.from, text: optText(f.key, g.from, g.from_label) }));
      } else {
        const others = L.groups.filter((g) => g.pick !== base);
        txt = `<b>${esc(short(base))}</b> unless ` + others.map((g) => `${esc(g.options.map((o) => optText(f.key, o.value, o.label)).join(" or "))} → <b>${esc(short(g.pick || "no option"))}</b>`).join("; ");
        alts = others.filter((g) => g.pick_id).map((g) => ({ pick: g.pick, value: g.options[0].value, text: optText(f.key, g.options[0].value, g.options[0].label) }));
      }
      const whys = [...new Set((f.ordered ? L.segments : L.groups).filter((g) => g.why).map((g) => g.why))].slice(0, 2);
      const wh = whys.length ? `<span class="dep-w muted small">${whys.map(esc).join(" ")}</span>` : "";
      (tags[l] = tags[l] || []).push(noun(f.key));
      return `<li><span class="dep-l">${cap(l)}</span><span class="dep-t">${txt}.</span>${wh}
        <span class="dep-b">${alts.slice(0, 3).map((a) => `<button type="button" class="pick-this" data-set-k="${esc(f.key)}" data-set-v="${esc(JSON.stringify(a.value))}" aria-label="Pick this: set ${esc(noun(f.key))} to ${esc(a.text)}, which gives ${esc(cap(l))} ${esc(a.pick)}">Pick ${esc(a.text)}</button>`).join("")}</span></li>`;
    }).join("");
    return `<div class="dep-f"><p class="dep-q">Depends on ${esc(noun(f.key))}${infoBtn(fieldTerms(f.key).slice(0, 1))}</p><ul>${lines}</ul></div>`;
  }).join("");
  Object.entries(tags).forEach(([l, ns]) => { const tag = $(`[data-dep="${l}"]`); if (tag) { tag.hidden = false; tag.textContent = `depends on ${ns.map((n) => n.replace(/^your /, "")).join(" and ")}`; } });
  const inert = s.fields.filter((f) => !f.matters.length).map((f) => noun(f.key));
  const stale = S.sensKey !== sensKey();
  box.innerHTML = `<section class="dep${stale ? " stale" : ""}" aria-label="What depends on your unknown answers"${stale ? ' aria-busy="true"' : ""}>
    <p class="dep-h"><b>Not sure about ${unknown.length === 1 ? "1 answer" : `${unknown.length} answers`}</b> <span class="muted">· each tested one at a time across its plausible values (${s.runs} engine runs)</span></p>
    ${robust.length ? `<p class="dep-ok">${ICON.check}<span><b>Robust:</b> ${esc(robust.join(", "))}. Same pick whatever ${unknown.length === 1 ? "that answer is" : "those answers are"}.</span></p>` : ""}
    ${blocks}
    ${inert.length ? `<p class="dep-in muted small">No effect on any layer: ${esc(inert.join(", "))}.</p>` : ""}
    ${s.skipped && s.skipped.length ? `<p class="dep-in muted small">Not tested (too many unknowns at once): ${esc(s.skipped.map(noun).join(", "))}.</p>` : ""}
  </section>`;
}

function onPickThis(btn) {
  const k = btn.dataset.setK, v = JSON.parse(btn.dataset.setV), before = structuredClone(S.answers[k]);
  S.answers[k] = v;
  S.unknown.delete(k);
  commit([k], { [k]: before });
}

/* ------------------------------------------------------------------ mobile summary bar + desktop sticky offset */
function renderSummaryBar(prev) {
  const bar = $("#sumbar"), r = S.result;
  if (!bar) return;
  if (!r || !r.feasible) { bar.hidden = true; return; }
  bar.hidden = false;
  $("#sumbar-picks").innerHTML = LAYERS.map((l) => {
    const n = short(r.stack[l].pick.name), was = prev && prev.feasible ? prev.stack[l].pick.name : null;
    return `<span class="sb-p${was && was !== r.stack[l].pick.name ? " changed" : ""}"><small>${cap(l).slice(0, 2)}</small>${esc(n)}</span>`;
  }).join("");
  $("#sumbar-cost").textContent = costText(r);
  $("#sumbar-btn").setAttribute("aria-label", `Your stack: ${LAYERS.map((l) => `${l} ${r.stack[l].pick.name}`).join(", ")}; monthly cost ${costText(r)}. Show the full result`);
}

/** Desktop: questions and result are two panes that each scroll on their own and together fill the
    window below the header. This measures where the workspace starts so the panes end at the window's bottom. */
function stickyOffset() {
  const work = document.querySelector(".work");
  if (work) document.documentElement.style.setProperty("--work-top", `${Math.round(work.getBoundingClientRect().top + scrollY)}px`);
}

/* ------------------------------------------------------------------ what-if sliders */
const TEAM_STEPS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200];
const SLIDERS = [
  { key: "dau", label: "Daily users", min: 1, max: 7, step: 0.01,
    toPos: (v) => Math.log10(Math.max(10, +v || 10)), fromPos: (p) => nice(Math.pow(10, p)), txt: (v) => compact(v) },
  { key: "budget_monthly", label: "Monthly budget", min: 0, max: 100, step: 1,
    toPos: (v) => (+v <= 0 ? 0 : Math.max(1, Math.min(100, (Math.log10(+v) / budgetSpan()) * 100))),
    fromPos: (p) => (p <= 0 ? 0 : nice(Math.pow(10, (p / 100) * budgetSpan()))), txt: (v) => (+v === 0 ? `${sym()}0` : `${sym()}${compact(v)}`) },
  { key: "team_size", label: "Team size", min: 0, max: TEAM_STEPS.length - 1, step: 1,
    toPos: (v) => TEAM_STEPS.reduce((bi, x, i) => (Math.abs(x - v) < Math.abs(TEAM_STEPS[bi] - v) ? i : bi), 0),
    fromPos: (p) => TEAM_STEPS[Math.round(p)], txt: (v) => `${v} ${+v === 1 ? "person" : "people"}` },
];
const budgetSpan = () => (S.answers.currency === "INR" ? 7 : 5);

function renderWhatIf(force = false) {
  const box = $("#whatif");
  if (!box) return;
  if (!$(".wi", box) || force) {
    box.innerHTML = `<div class="wi"><div class="wi-h"><h3>What if…</h3><span>Drag to re-run the engine live; the questions on the left move with you</span></div>
      <div class="wi-grid">${SLIDERS.map((s) => `<div class="sl"><span class="sl-l"><label for="sl-${s.key}">${s.label}</label>${s.key === "dau" ? infoBtn("dau") : ""}</span><output id="so-${s.key}" for="sl-${s.key}" class="mono"></output>
        <input type="range" id="sl-${s.key}" data-k="${s.key}" min="${s.min}" max="${s.max}" step="${s.step}"></div>`).join("")}</div>
      <ul class="wi-note" id="wi-note" aria-live="polite">${S.lastNote || "<li>Move a slider or change any answer: changed layers light up in gold, with the reason.</li>"}</ul></div>`;
    $$("input[type=range]", box).forEach((inp) => inp.addEventListener("input", onSlide));
  }
  syncSliders();
}

function syncSliders() {
  SLIDERS.forEach((s) => {
    const inp = $(`#sl-${s.key}`);
    if (!inp) return;
    const v = S.answers[s.key] ?? 0;
    if (document.activeElement !== inp) inp.value = s.toPos(v);
    paintSlider(inp);
    $(`#so-${s.key}`).textContent = s.txt(v);
    inp.setAttribute("aria-valuetext", s.key === "budget_monthly" ? `${money(v)} per month` : s.txt(v));
  });
}
function paintSlider(inp) {
  const p = ((inp.value - inp.min) / (inp.max - inp.min)) * 100;
  inp.style.setProperty("--fill", `${p.toFixed(1)}%`);
}

/** A slider is just another control on the same answer model: it updates S.answers, the chips and the refine field. */
function onSlide(e) {
  const inp = e.target, s = SLIDERS.find((x) => x.key === inp.dataset.k);
  const old = S.answers[s.key] ?? 0, v = s.fromPos(+inp.value);
  paintSlider(inp);
  if (v === old && !S.unknown.has(s.key)) return;
  S.answers[s.key] = v;
  commit([s.key], { [s.key]: old });
}

/* ================================================================== language-model features (all optional)
   The rules decide every pick. The model only reads free text (brief, what-if) and words the summary, and the
   server checks everything it returns, so each feature also works with no API key (rule reader / template text). */

/** Which answers a quick question sets. "Must-haves" stands for four answers. */
const quickKeys = (Q) => (Q.key === "must" ? ["realtime", "offline", "seo", "platforms"] : [Q.key, Q.key2].filter(Boolean));
const srcBadge = (f) => `<span class="src src-${esc(f.source)}" title="${f.source === "rule" ? "read by the pattern reader" : "read by the language model; the quote was found in your text"}">${f.source === "rule" ? "rule" : "LLM"}</span>`;

/** One line saying whether the language model is on and what it did on the last request. */
function setLlmNote(llm) {
  const el = $("#brief-llm");
  if (!el) return;
  el.textContent = !llm.enabled ? "Language model: off (no API key), so only the rule reader runs."
    : llm.error ? `Language model: on, but it did not answer (${llm.error}). Rule reader only.`
    : llm.used ? `Language model: on (${llm.model}).` : "Language model: on.";
}

/* ------------------------------------------------------------------ describe your project */
async function fillFromBrief() {
  const text = $("#brief-text").value.trim(), out = $("#brief-out"), btn = $("#brief-btn");
  out.hidden = false;
  if (!text) { out.innerHTML = `<p class="muted small">Write a sentence or two about your project first.</p>`; return; }
  btn.disabled = true;
  out.innerHTML = `<p class="muted small">Reading your description...</p>`;
  try {
    applyBrief(await api("/api/brief", { text }));
  } catch (e) {
    out.innerHTML = `<p class="muted small" role="alert">Could not read the description. ${esc(e.message)}</p>`;
  } finally { btn.disabled = false; }
}

/** Put the answers found in the description into the answer model, mark where each came from, then continue with the open questions. */
function applyBrief(r) {
  const keys = Object.keys(r.fields).filter(fieldByKey), before = {};
  keys.forEach((k) => { before[k] = structuredClone(S.answers[k]); S.answers[k] = structuredClone(r.fields[k].value); });
  if (keys.length) { S.cause = "your project description"; commit(keys, before); }
  keys.forEach((k) => (S.briefSrc[k] = r.fields[k]));
  paintBriefMarks();
  setLlmNote(r.llm);
  const open = QUICK.filter((Q) => {
    const ks = quickKeys(Q);
    return !ks.some((k) => r.fields[k]);
  });
  const rows = keys.map((k) => {
    const f = r.fields[k];
    return `<li><span class="b-k">${esc(splitLabel(fieldByKey(k).label)[0])}</span><b>${esc(valText(k, f.value))}</b>${srcBadge(f)}<q class="b-q">${esc(f.evidence)}</q>${f.note ? `<small class="muted"> ${esc(f.note)}</small>` : ""}</li>`;
  }).join("");
  const dropped = (r.llm.dropped || []).length;
  $("#brief-out").innerHTML = keys.length
    ? `<p class="an-h"><b>${keys.length} ${keys.length === 1 ? "answer" : "answers"} filled</b> <span class="muted small">· each shows where it came from</span></p>
       <ul class="b-list">${rows}</ul>
       ${dropped ? `<p class="muted small">${dropped} value${dropped === 1 ? "" : "s"} from the language model ${dropped === 1 ? "was" : "were"} dropped: invalid for the question, or its quote was not in your text.</p>` : ""}
       ${open.length ? `<p class="muted small">Still open: ${open.map((Q) => esc(Q.title.replace(/\?$/, ""))).join("; ")}. The questions below are the ones left to answer.</p>` : ""}`
    : `<p class="muted small">Nothing in that text could be read as an answer. Say who uses it and how many, the budget, the team and what it must do, or use the questions below.</p>`;
  if (keys.length) askNext();
}

/** Small "from text" marker on each quick question that was filled from the description (hover for the quote). */
function paintBriefMarks() {
  $$("#quick .q-src").forEach((el) => el.remove());
  for (const Q of QUICK) {
    const fs = quickKeys(Q).map((k) => S.briefSrc[k]).filter(Boolean), legend = $(`#q-${Q.id} legend`);
    if (!fs.length || !legend) continue;
    const m = document.createElement("span");
    m.className = `q-src src-${fs[0].source}`;
    m.textContent = fs.some((f) => f.source === "llm") ? "from text · LLM" : "from text · rule";
    m.title = fs.map((f) => `“${f.evidence}”`).join(", ");
    legend.insertBefore(m, $(".q-ro", legend));
  }
}

/* ------------------------------------------------------------------ plain-English summary */
const summaryKey = () => JSON.stringify(sent());

function renderSummary() {
  const box = $("#summary");
  if (!box) return;
  const s = S.summary && S.summary.key === summaryKey() ? S.summary.data : null;
  if (!s) {
    box.innerHTML = `<div class="sum"><div class="sum-h"><h3>Plain-English summary</h3>
      <button type="button" class="link-btn" id="sum-go">Write summary</button></div>
      <p class="muted small">A language model re-words the engine's own facts. Its text is shown only if every technology and number in it appears in those facts; otherwise you get the engine's template text.</p></div>`;
    return;
  }
  const ok = s.source === "llm" && s.checked;
  const why = ok ? "" : !s.llm_enabled ? "The language model is off (no API key), so this is the engine's own template text."
    : `The model's text did not pass the check${s.errors && s.errors.length ? ` (${esc(s.errors[0])})` : ""}, so this is the engine's template text.`;
  box.innerHTML = `<div class="sum"><div class="sum-h"><h3>Plain-English summary</h3>
      <span class="sum-badge ${ok ? "ok" : "fb"}">${ok ? `${ICON.check}checked against engine facts` : "template fallback"}</span>
      <button type="button" class="link-btn" id="sum-go">Write again</button></div>
    ${s.overall ? `<p class="sum-all">${esc(s.overall)}</p>` : ""}
    <dl class="sum-l">${LAYERS.filter((l) => s.layers[l]).map((l) => `<dt>${esc(LAYER_NAME[l])}</dt><dd>${esc(s.layers[l])}</dd>`).join("")}</dl>
    <p class="muted small">${why}${ok ? ` Written by ${esc(s.model)}; the picks and scores come from the rules.` : ""}</p></div>`;
}

async function loadSummary() {
  const key = summaryKey(), btn = $("#sum-go");
  if (btn) { btn.disabled = true; btn.textContent = "Writing..."; }
  try {
    S.summary = { key, data: await api("/api/summary", sent()) };
  } catch (e) {
    S.summary = null;
    const box = $("#summary"); if (box) box.insertAdjacentHTML("beforeend", `<p class="muted small" role="alert">Could not write the summary. ${esc(e.message)}</p>`);
    if (btn) { btn.disabled = false; btn.textContent = "Write summary"; }
    return;
  }
  renderSummary();
}

/* ------------------------------------------------------------------ second opinion */
const secondKey = () => JSON.stringify(sent());
const SECOND_INTRO = "A language model picks its own stack for these answers; the rules then grade it (hard requirements, score, cost). The recommendation above is not changed.";

function renderSecond() {
  const box = $("#second");
  if (!box) return;
  const on = !!(S.health && S.health.llm_enabled);
  const x = S.second && S.second.key === secondKey() ? S.second.data : null;
  if (!x || !x.ok) {
    const note = !on ? "Needs a language-model API key, which is not set, so this is off."
      : x ? esc(x.note) : esc(SECOND_INTRO);
    box.innerHTML = `<div class="sum"><div class="sum-h"><h3>Second opinion</h3>
      <button type="button" class="link-btn" id="second-go"${on ? "" : " disabled"}>${x ? "Try again" : "Ask for a second opinion"}</button></div>
      <p class="muted small">${note}</p></div>`;
    return;
  }
  const usd = (v) => `$${fmt(Math.abs(v))}`;
  const rows = LAYERS.map((l) => {
    const y = x.layers[l];
    const bad = y.ruled_out.length;
    return `<tr class="${y.agree ? "so-same" : bad ? "so-bad" : ""}"><th scope="row">${esc(LAYER_NAME[l])}</th><td>${esc(y.model || "no valid answer")}</td><td>${esc(y.engine)}</td>
      <td>${y.agree ? "agree" : bad ? "model's pick ruled out" : "differ"}</td></tr>`;
  }).join("");
  box.innerHTML = `<div class="sum"><div class="sum-h"><h3>Second opinion</h3>
      <span class="sum-badge ${x.breaks.length ? "fb" : "ok"}">${x.breaks.length ? `model breaks ${x.breaks.length} hard requirement${x.breaks.length > 1 ? "s" : ""}` : "no hard requirement broken"}</span>
      <button type="button" class="link-btn" id="second-go">Ask again</button></div>
    <p class="sum-all">${esc(x.summary)}</p>
    <table class="so-t"><thead><tr><th></th><th>Model</th><th>Engine</th><th></th></tr></thead><tbody>${rows}</tbody></table>
    <ul class="so-v">${x.verdicts.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
    <p class="muted small">The model (${esc(x.model)}) gives no costs, reasons or sources; the grades and costs come from the rules, so the engine's pick stays the recommendation.</p></div>`;
}

async function loadSecond() {
  const key = secondKey(), btn = $("#second-go");
  if (btn) { btn.disabled = true; btn.textContent = "Asking..."; }
  try {
    S.second = { key, data: await api("/api/second-opinion", sent()) };
  } catch (e) {
    S.second = { key, data: { ok: false, note: `Could not get a second opinion. ${e.message}` } };
  }
  renderSecond();
}

/* ------------------------------------------------------------------ "What if..." in words */
function renderWhatIfText() {
  const box = $("#whatif-q");
  if (!box || $(".wq", box)) return;
  box.innerHTML = `<form class="wq" id="wq-form"><label for="wq-in">Or ask in words</label>
    <div class="wq-row"><input type="text" id="wq-in" maxlength="400" placeholder="What if we had ten times the users?" autocomplete="off">
    <button type="submit" class="ex" id="wq-go">Ask</button></div>
    <div id="wq-out" class="muted small" aria-live="polite"></div></form>`;
  $("#wq-form").onsubmit = (e) => { e.preventDefault(); askWhatIf(); };
}

/** Send the question to /api/whatif; apply the changes it returns through the normal answer model, so the engine re-runs and the gold change note shows. */
async function askWhatIf() {
  const q = $("#wq-in").value.trim(), out = $("#wq-out"), btn = $("#wq-go");
  if (!q) return;
  btn.disabled = true; out.textContent = "Reading the question...";
  try {
    const r = await api("/api/whatif", { answers: sent(), question: q });
    const keys = Object.keys(r.changes).filter(fieldByKey), before = {};
    if (!keys.length) {
      out.textContent = r.llm.enabled ? "Nothing in that question maps to a change of an answer."
        : "Nothing found. The language model is off (no API key), so only plain numbers and clear words work, such as “team of 8” or “budget $0”.";
      return;
    }
    keys.forEach((k) => { before[k] = structuredClone(S.answers[k]); S.answers[k] = structuredClone(r.changes[k].value); });
    S.cause = `your what-if “${q}”`;
    commit(keys, before);
    out.innerHTML = keys.map((k) => `<span class="wq-c">${esc(splitLabel(fieldByKey(k).label)[0])}: <s>${esc(valText(k, before[k]))}</s> → <b>${esc(valText(k, S.answers[k]))}</b> ${srcBadge(r.changes[k])}<q class="b-q">${esc(r.changes[k].evidence)}</q></span>`).join("");
  } catch (e) {
    out.textContent = `Could not read the question. ${e.message}`;
  } finally { btn.disabled = false; }
}

/* ------------------------------------------------------------------ detail panels */
function bindExports() {
  $("#exp-json").onclick = () => download(`stacksense-${slug()}.json`, JSON.stringify(S.result, null, 2), "application/json");
  $("#exp-md").onclick = async (e) => {
    const b = e.currentTarget; b.disabled = true;
    try { download(`stacksense-${slug()}.md`, await api("/api/export/markdown", sent()), "text/markdown"); }
    catch (err) { b.title = err.message; }
    b.disabled = false;
  };
  $("#exp-adr").onclick = async (e) => {
    const b = e.currentTarget; b.disabled = true;
    try { download(`stacksense-${slug()}-adr.md`, await api("/api/export/adr", sent()), "text/markdown"); }
    catch (err) { b.title = err.message; }
    b.disabled = false;
  };
  const note = (t) => { $("#share-note").textContent = t; };
  $("#share-copy").onclick = async () => {
    const url = shareUrl();
    try { await navigator.clipboard.writeText(url); note("Link copied."); }
    catch (e) { history.replaceState(null, "", url.slice(url.indexOf("#"))); note("Copy the address bar: it now holds your answers."); }
  };
  $("#share-save").onclick = () => download(`stacksense-${slug()}-answers.json`, Share.toFile(sent(), S.unknown), "application/json");
  $("#share-load").onclick = () => { note(""); $("#share-file").click(); };
  $("#share-file").onchange = async (e) => {
    const f = e.target.files[0]; e.target.value = "";
    if (!f) return;
    const r = Share.fromFile(await f.text(), (k) => !!fieldByKey(k));
    if (!r) { note("That file is not a JSON answers file."); return; }
    await loadProject(r.answers, r.unknown);
    const n = Object.keys(r.answers).length;
    note(`Loaded ${n} answer${n === 1 ? "" : "s"}${r.ignored.length ? `; ignored unknown: ${r.ignored.join(", ")}` : ""}.`);
  };
  $("#do-print").onclick = async () => { try { await loadGrowth(); } catch (e) { /* print without it */ } window.print(); };
}

function openPanel(id, { keep = false, layer = null, focus = false } = {}) {
  if (!keep && S.panel === id && !layer) id = null; /* clicking the open drawer closes it */
  S.panel = id;
  if (layer) S.whyLayer = layer;
  $$(".drawer-b").forEach((b) => b.setAttribute("aria-expanded", String(b.dataset.open === id)));
  $$(".panel").forEach((p) => (p.hidden = p.id !== `panel-${id}`));
  if (id === "why") selectWhy(S.whyLayer);
  if (id === "growth") showGrowth();
  if (id && !keep) {
    const p = $(`#panel-${id}`);
    p.scrollIntoView({ behavior: smooth(), block: "nearest" });
    if (focus) { p.setAttribute("tabindex", "-1"); p.focus({ preventScroll: true }); }
  }
}

function renderPanels() {
  const r = S.result;
  if (!r.feasible) {
    $$(".panel").forEach((p) => (p.innerHTML = `<p class="muted">Available once a stack satisfies every hard constraint.</p>`));
    $("#panel-inputs").innerHTML = inputsPanel();
    return;
  }
  $("#panel-why").innerHTML = whyPanel();
  $("#panel-arch").innerHTML = archPanel();
  $("#panel-cost").innerHTML = costPanel();
  $("#panel-alts").innerHTML = altsPanel();
  $("#panel-inputs").innerHTML = inputsPanel();
  $("#panel-growth").innerHTML = `<p class="muted g-wait">Open this drawer to project the stack at 10× and 100× your users.</p>`;
}

/* why: per-layer trace */
function whyPanel() {
  const r = S.result;
  return `<div class="seg" role="tablist" aria-label="Layer">${LAYERS.map((l) => `<button type="button" role="tab" class="seg-b" data-why-layer="${l}" aria-selected="false" aria-controls="why-${l}-p">${cap(l)}</button>`).join("")}</div>` +
    LAYERS.map((l) => {
      const s = r.stack[l], e = s.explanation, p = s.pick, vs = e.vs_runner_up;
      const base = e.input_contributions.find((c) => c.input === "baseline");
      const ans = e.input_contributions.filter((c) => c.input !== "baseline");
      const sum = ans.reduce((a, c) => a + c.points, 0);
      const bd = p.breakdown.filter((b) => b.weight > 0).sort((a, b) => b.points - a.points)
        .map((b) => ({ html: `${esc(b.label)} <small class="mono">${b.score.toFixed(1)}/5 × w${fmt(b.weight, 1)}</small>`, value: b.points }));
      const srcs = [...new Set(p.sources.concat(r.compatibility.filter((c) => (c.layers || []).includes(l) && c.source).map((c) => c.source)))];
      return `<article class="why-l" id="why-${l}-p" role="tabpanel" data-layer="${l}" hidden>
        <header class="wl-h"><div><p class="kicker">${esc(s.title)}</p><h3>${esc(p.name)}</h3>
          ${s.managed_offering ? `<p class="muted small">Offering: ${esc(s.managed_offering)}</p>` : ""}
          ${s.runs_here && !s.optional_host ? `<p class="muted small">${esc(s.runs_here)}</p>` : ""}
          ${s.api_host ? `<p class="muted small">API host: <b>${esc(s.api_host.name)}</b> (${s.api_host.score.toFixed(1)}). ${esc(s.api_host.why)}</p>` : ""}</div>
          <p class="wl-s"><b class="mono">${p.score.toFixed(1)}</b><small>/100 · ${vs ? `margin over runner-up ${vs.margin.toFixed(1)}: ${confWord[e.confidence] || e.confidence}` : "no runner-up"}</small></p></header>
        ${e.paragraph ? `<p class="wl-para">${esc(plain(e.paragraph))}</p>` : ""}
        <div class="wl-grid">
          <section><h4>Why</h4>${list(e.why.concat(e.strengths.slice(0, 2)), "ticks")}</section>
          <section><h4>Which of your answers moved the score</h4>
            <p class="eq mono">baseline (the score before your answers) ${fmt(base ? base.points : 0, 1)} ${sum >= 0 ? "+" : "−"} your answers ${fmt(Math.abs(sum), 1)} = <b>${p.score.toFixed(1)}</b></p>
            ${divChart(ans.slice(0, 8).map((c) => ({ label: plain(c.label), value: c.points })))}</section>
        </div>
        ${vs ? `<p class="vs"><b>vs ${esc(vs.runner_up)}:</b> ${esc(plain(vs.text))}</p>` : ""}
        <div class="wl-grid">
          <section><h4>Trade-offs you accept</h4>${list(e.tradeoffs, "dash")}</section>
          <section><h4>Risks to plan for</h4>${e.risks.length ? list(e.risks, "dash") : '<p class="muted">None flagged for your answers.</p>'}</section>
        </div>
        <details class="sub"><summary>Score by criterion (score × weight)</summary>${hbars(bd, Math.max(...bd.map((x) => x.value), 1))}
          ${p.adjustments.length ? `<ul class="adj">${p.adjustments.map((a) => `<li><span class="mono ${a.delta > 0 ? "pos" : "neg"}">${a.delta > 0 ? "+" : ""}${a.delta}</span> ${esc(a.reason)}</li>`).join("")}</ul>` : ""}</details>
        ${whyNotSection(l, s)}
        <section class="cites"><h4>Cited sources</h4><ol>${srcs.map((x) => `<li>${link(x)}</li>`).join("")}</ol></section>
      </article>`;
    }).join("");
}

/** "Why not X?": the engine's list for this layer, a picker to compare any other option, and the full ranking. */
function whyNotSection(l, s) {
  const opts = [`<option value="${esc(s.pick.id)}">${esc(s.pick.name)} (the pick)</option>`]
    .concat(s.ranking.filter((x) => x.id !== s.pick.id).map((x) => `<option value="${esc(x.id)}">${esc(x.name)} · ${x.score.toFixed(1)}</option>`))
    .concat(s.excluded.map((x) => `<option value="${esc(x.id)}">${esc(x.name)} · ruled out</option>`));
  return `<section class="wn"><h4>Why not the others?</h4>
    ${(s.why_not || []).length ? `<ul class="wn-l">${s.why_not.map((x) => `<li><b>Why not ${esc(x.name)}?</b> <small class="muted">${esc(x.role)}</small> ${esc(x.text)}</li>`).join("")}</ul>` : ""}
    ${s.optional_host ? "" : `<p class="wn-ask"><label for="wn-${l}">Compare with</label> <select id="wn-${l}" data-wn-sel="${l}">${opts.join("")}</select>
      <button type="button" class="link-btn" data-whynot="${l}">Why not this?</button>
      <button type="button" class="link-btn" data-whynot="all" title="Uses the option chosen in each layer's 'Compare with' list">Grade the whole stack</button></p>
    <div class="wn-out" id="wn-out-${l}" aria-live="polite"></div>`}
    <details class="sub"><summary>Full ranking (${s.ranking.length} scored, ${s.excluded.length} ruled out)</summary>
      <ol class="wn-rank">${s.ranking.map((x) => `<li>${esc(x.name)} <span class="mono">${x.score.toFixed(1)}</span></li>`).join("")}</ol></details></section>`;
}

async function runRobustness() {
  const box = $("#rob-out");
  if (!box) return;
  box.innerHTML = `<p class="muted small">Running 60 engine runs…</p>`;
  try {
    const x = await api("/api/robustness", sent());
    if (!x.feasible) { box.innerHTML = `<p class="muted small">No feasible stack to test.</p>`; return; }
    box.innerHTML = `<table class="tbl"><thead><tr><th scope="col">Layer</th><th scope="col">Pick</th>${x.levels.map((n) => `<th scope="col" class="num">Held at ±${n}</th>`).join("")}<th scope="col">Most common other pick</th></tr></thead><tbody>${LAYERS.map((l) => {
      const rows = x.layers[l], o = rows[rows.length - 1].others[0];
      return `<tr><td>${cap(l)}</td><td>${esc(short(x.base[l]))}</td>${rows.map((y) => `<td class="num mono">${y.held_pct}%</td>`).join("")}<td>${o ? `${esc(short(o.name))} (${o.pct}%)` : "none"}</td></tr>`;
    }).join("")}</tbody></table>`;
  } catch (e) { box.innerHTML = `<p class="muted small">${esc(e.message)}</p>`; }
}

async function runWhyNot(layer) {
  const r = S.result, pins = {};
  if (layer === "all") LAYERS.forEach((l) => { const sel = $(`[data-wn-sel="${l}"]`); pins[l] = sel ? sel.value : r.stack[l].pick.id; });
  else pins[layer] = $(`[data-wn-sel="${layer}"]`).value;
  const at = layer === "all" ? S.whyLayer || "frontend" : layer, box = $(`#wn-out-${at}`);
  if (!box) return;
  box.innerHTML = `<p class="muted small">Re-running the search with that choice fixed and trying single answer changes…</p>`;
  try {
    const x = await api("/api/whynot", { answers: sent(), pins });
    if (!x.ok) { box.innerHTML = `<p class="muted small">${esc(x.error)}</p>`; return; }
    const usd = (v) => `$${fmt(Math.abs(v))}`;
    const rows = Object.values(x.layers).filter((y) => !y.is_pick && y.compare).map((y) => `<li>${esc(y.compare)}.</li>`);
    if (Object.keys(x.other_layers_changed).length) rows.push(`<li>Its best stack also changes ${esc(Object.entries(x.other_layers_changed).map(([k, v]) => `${k} to ${v}`).join(", "))}.</li>`);
    x.rules_lost.forEach((t) => rows.push(`<li>Loses: ${esc(t)}</li>`));
    x.rules_gained.forEach((t) => rows.push(`<li>Adds: ${esc(t)}</li>`));
    if (x.cost.difference) rows.push(`<li>Estimated minimum cost ${x.cost.difference > 0 ? "rises" : "falls"} by ${usd(x.cost.difference)} a month.</li>`);
    const ch = x.changes.length ? `<p class="small"><b>It would be the pick if</b> (one answer changed, ${x.changes_tested} tried): ${x.changes.map((c) => `${esc(c.field)} = ${esc(c.label)}`).join("; ")}.</p>`
      : x.changes_tested ? `<p class="small muted">No single answer change makes it the pick (${x.changes_tested} tried).</p>` : "";
    box.innerHTML = `<div class="wn-res"><p><b>${esc(x.verdict)}</b>${x.approximate ? ' <small class="muted">(approximate: scored despite a hard constraint)</small>' : ""}</p>${rows.length ? `<ul>${rows.join("")}</ul>` : ""}${ch}</div>`;
  } catch (e) { box.innerHTML = `<p class="muted small">${esc(e.message)}</p>`; }
}

function selectWhy(l) {
  S.whyLayer = l;
  $$("[data-why-layer]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.whyLayer === l)));
  $$(".why-l").forEach((a) => (a.hidden = a.dataset.layer !== l));
}

/* cost */
function costPanel() {
  const r = S.result, c = r.cost, pr = r.profile || {}, fx = c.total_low > 0 && c.total_low_inr ? c.total_low_inr / c.total_low : FX;
  const maxv = Math.max(c.total_high, c.budget_usd, 1) * 1.12;
  return `<div class="budget"><div class="b-track"><span class="b-range" style="--l:${((c.total_low / maxv) * 100).toFixed(2)}%;--w:${Math.max(1, ((c.total_high - c.total_low) / maxv) * 100).toFixed(2)}%"></span>
      <span class="b-line" style="--l:${((c.budget_usd / maxv) * 100).toFixed(2)}%"><span>budget ${usd(c.budget_usd)}</span></span></div>
    <p class="muted small">Band: estimated monthly range. Line: your budget${pr.currency === "INR" ? ` (₹${fmt(pr.budget_monthly)})` : ""}.</p></div>
    <table class="tbl"><thead><tr><th scope="col">Component</th><th scope="col" class="num">USD / month</th><th scope="col" class="num">INR / month</th></tr></thead>
    <tbody>${c.lines.map((x) => `<tr><td>${esc(x.component)}${x.basis ? `<br><small class="muted">${esc(x.basis)}</small>` : ""}</td><td class="num mono">${rng(x.low, x.high, usd)}</td><td class="num mono">${rng(x.low * fx, x.high * fx, (v) => `₹${fmt(v)}`)}</td></tr>`).join("")}</tbody>
    <tfoot><tr><th scope="row">Total</th><td class="num mono">${rng(c.total_low, c.total_high, usd)}</td><td class="num mono">${rng(c.total_low * fx, c.total_high * fx, (v) => `₹${fmt(v)}`)}</td></tr></tfoot></table>
    <p class="muted small">${esc(c.note)} ${r.derived.fx_note ? esc(r.derived.fx_note) : ""}</p>`;
}

/* alternatives + sensitivity */
function altsPanel() {
  const r = S.result;
  const cf = r.counterfactuals.map((x) => `<li><span class="cf-c">${esc(x.change)}</span><span>${x.effects.length ? x.effects.map((f) => `${esc(cap(f.layer))}: <s>${esc(short(f.from))}</s> → <b>${esc(short(f.to))}</b>${f.why ? `<br><small class="muted">${esc(f.why)}</small>` : ""}`).join("<br>") : `<span class="muted">${esc(x.note || "no change")}</span>`}</span></li>`).join("");
  return `<div class="wl-grid">
    <section><h4>Next-best stacks</h4><ol class="alt-st">${r.alternative_stacks.map((a) => `<li><span>${LAYERS.map((l) => esc(short(a.stack[l]))).join(" + ")}</span><span class="mono">${a.score.toFixed(1)} <small class="neg">(${a.delta.toFixed(1)})</small></span></li>`).join("")}</ol></section>
    <section><h4>Runner-up per layer</h4><ul class="alt-st">${LAYERS.map((l) => { const vs = r.stack[l].explanation.vs_runner_up; return `<li><span><b>${cap(l)}:</b> ${vs ? esc(short(vs.runner_up)) : "none eligible"}</span><span class="mono">${vs ? `${vs.margin >= 0 ? "−" : "+"}${Math.abs(vs.margin).toFixed(2)}` : ""}</span></li>`; }).join("")}</ul></section>
  </div>
  <section><h4>How stable is this pick?</h4><p class="small muted">The 1-5 scores in the knowledge base are judgement calls. This re-runs the engine 30 times per level with every score shifted at random (seeded by your answers) and counts how often each layer keeps its pick.</p>
    <p><button type="button" class="link-btn" id="rob-go">Measure under score noise</button></p><div id="rob-out" aria-live="polite"></div></section>
  <section><h4>What would change the recommendation</h4><ul class="cf">${cf || "<li>No tested single-answer change switches a layer.</li>"}</ul></section>
  ${LAYERS.some((l) => r.stack[l].excluded.length) ? `<details class="sub"><summary>Ruled out (requirement not met)</summary><ul class="excl">${LAYERS.flatMap((l) => r.stack[l].excluded.map((x) => `<li><b>${esc(x.name)}</b> <span class="muted">${esc(x.reasons.join("; "))}</span></li>`)).join("")}</ul></details>` : ""}`;
}

/* inputs, weights, assumptions, compatibility */
function inputsPanel() {
  const r = S.result, d = r.derived || {};
  const ws = r.weights.filter((w) => w.weight > 0).sort((a, b) => b.weight - a.weight), wmax = Math.max(...ws.map((w) => w.weight), 1);
  return `<p class="muted small">Every criterion starts at a baseline weight (its standard importance before your answers change it); your answers add or remove weight. Derived: ${esc(d.tier_label || "")}, about ${fmt(d.peak_rps || 0)} peak req/s (${esc(d.rps_source || "")}), about ${fmt(d.data_12mo_gb || 0)} GB after 12 months.</p>
    <div class="weights">${ws.map((w) => {
      const drv = w.drivers.filter((x) => x.input !== "baseline");
      return `<div class="w-row"><span class="w-lab">${esc(w.label)}</span><span class="h-track"><i style="--w:${((w.weight / wmax) * 100).toFixed(1)}%"></i></span><span class="mono w-num">${fmt(w.weight, 1)}</span>
        ${drv.length ? `<span class="w-drv">${drv.map((x) => `<span><b class="mono ${x.amount < 0 ? "neg" : "pos"}">${x.amount > 0 ? "+" : ""}${x.amount}</b> ${esc(x.reason)}</span>`).join("")}</span>` : ""}</div>`;
    }).join("")}</div>
    ${r.compatibility.length ? `<h4>How the picks work together</h4><ul class="compat">${r.compatibility.map((x) => `<li><span class="mono ${x.delta > 0 ? "pos" : "neg"}">${x.delta > 0 ? "+" : ""}${x.delta}</span><span>${esc(x.note)} ${x.source ? link(x.source) : ""}</span></li>`).join("")}</ul>` : ""}
    ${assumeList(r.assumptions.filter((a) => a.kind === "default"), "Defaults used", false)}
    ${assumeList(r.assumptions.filter((a) => a.kind !== "default"), "Implied by your answers", true)}`;
}

function assumeList(items, title, withReason) {
  if (!items.length) return "";
  const val = (v) => (Array.isArray(v) ? v.join(", ") || "none" : typeof v === "number" ? fmt(v) : v);
  return `<details class="sub"><summary>${title} (${items.length})</summary><ul class="assume">${items.map((a) =>
    `<li>${esc(a.label || fieldByKey(a.field)?.label || a.field)} = <b>${esc(val(a.value))}</b>${withReason ? ` <span class="muted">${esc(a.reason)}</span>` : ""}</li>`).join("")}</ul></details>`;
}

/* ------------------------------------------------------------------ growth path: 1x / 10x / 100x users */
const G_MULT = [1, 3, 10, 30, 100];
const G_COLS = [0, 2, 4];

async function loadGrowth() {
  if (!S.result || !S.result.feasible) return null;
  const key = JSON.stringify(S.answers);
  if (S.growth && S.growthKey === key) return S.growth;
  if (S.growthBusy && S.growthBusy.key === key) return S.growthBusy.p;
  const base = Math.max(1, +S.result.profile.dau || 1);
  const p = Promise.all(G_MULT.map((m) => {
    const a = sent();
    a.dau = Math.min(2e9, Math.round(base * m));
    if (a.peak_rps != null && a.peak_rps !== "") a.peak_rps = +a.peak_rps * m;
    if (a.peak_concurrent != null && a.peak_concurrent !== "") a.peak_concurrent = Math.round(+a.peak_concurrent * m);
    return api("/api/recommend?lite=1", a);
  })).then((runs) => {
    S.growthBusy = null;
    if (JSON.stringify(S.answers) !== key) return null;
    S.growth = { base, runs }; S.growthKey = key;
    return S.growth;
  }, (e) => { S.growthBusy = null; throw e; });
  S.growthBusy = { key, p };
  return p;
}

async function showGrowth() {
  const el = $("#panel-growth");
  if (!S.result || !S.result.feasible) return;
  if (!(S.growth && S.growthKey === JSON.stringify(S.answers))) el.innerHTML = `<p class="muted g-wait">Running the engine at 1×, 3×, 10×, 30× and 100× your users…</p>`;
  try {
    const g = await loadGrowth();
    if (g) el.innerHTML = growthHtml(g);
  } catch (e) { el.innerHTML = `<p class="muted" role="alert">${esc(e.message)}</p>`; }
}

function growthHtml(g) {
  const { base, runs } = g, users = (i) => base * G_MULT[i];
  const ok = runs.every((x) => x.feasible);
  if (!ok) return `<p class="muted">At least one growth step has no feasible stack. Raise the budget slider and try again.</p>`;
  const name = (i, l) => runs[i].stack[l].pick.name;
  const stays = [], moves = [];
  const rows = LAYERS.map((l) => {
    const cells = G_COLS.map((ci, k) => {
      if (k === 0) return `<td><span class="g-n">${esc(short(name(ci, l)))}</span></td>`;
      const pc = G_COLS[k - 1];
      if (name(ci, l) === name(pc, l)) return `<td class="g-same"><span class="g-n">${esc(short(name(ci, l)))}</span></td>`;
      let j = pc + 1;
      while (j < ci && name(j, l) === name(pc, l)) j++;
      moves.push(`${cap(l)} → ${short(name(ci, l))} at about ${compact(users(j))} users`);
      return `<td class="g-chg"><span class="g-n">${esc(short(name(ci, l)))}</span><small>from ~${compact(users(j))} users</small></td>`;
    }).join("");
    if (G_COLS.every((ci) => name(ci, l) === name(0, l))) stays.push(short(name(0, l)));
    return `<tr><th scope="row">${cap(l)}</th>${cells}</tr>`;
  }).join("");
  const costRow = G_COLS.map((ci) => { const c = runs[ci].cost; return `<td class="mono">${rng(c.total_low, c.total_high, usd)}<small class="st st-${esc(c.status)}">${esc(c.status)}</small></td>`; }).join("");
  const tierRow = G_COLS.map((ci) => `<td>${esc(runs[ci].derived.tier_label)}</td>`).join("");
  const scoreRow = G_COLS.map((ci) => `<td class="mono">${runs[ci].stack_score.toFixed(1)}</td>`).join("");
  return `<p class="g-sum">${stays.length ? `<b>Stays:</b> ${esc(stays.join(", "))}. ` : ""}${moves.length ? `<b>Changes:</b> ${esc(moves.join("; "))}.` : "<b>No layer changes</b> up to 100× your users."}</p>
    <table class="tbl growth"><thead><tr><th scope="col"><span class="sr-only">Layer</span></th>${G_COLS.map((ci) => `<th scope="col"><span class="g-x mono">${G_MULT[ci]}×</span> ${compact(users(ci))} users/day</th>`).join("")}</tr></thead>
    <tbody>${rows}<tr class="g-meta"><th scope="row">Monthly cost</th>${costRow}</tr><tr class="g-meta"><th scope="row">Size of project</th>${tierRow}</tr><tr class="g-meta"><th scope="row">Score</th>${scoreRow}</tr></tbody></table>
    <p class="muted small">Only daily users change; budget, team and every other answer stay as you set them. Gold cells mark a switch.</p>`;
}

/* ------------------------------------------------------------------ architecture diagram (inline SVG) */
const SIDE_ROLES = ["Cache", "Ingestion buffer", "Background jobs", "Realtime", "Search", "Vector search", "Object storage", "Secondary store (graph)"];

function wrap(text, n) {
  const words = String(text).split(/\s+/), lines = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > n && cur) { lines.push(cur); cur = w; } else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur);
  if (lines.length > 2) { lines.length = 2; lines[1] = lines[1].slice(0, n - 1) + "…"; }
  return lines;
}

function node(x, y, w, h, kicker, title, sub, cls = "") {
  const t = wrap(title, Math.floor((w - 24) / 8.2));
  const ty = y + 35;
  return `<g class="n ${cls}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10"/>
    <text x="${x + 12}" y="${y + 17}" class="n-k">${esc(kicker)}</text>
    ${t.map((ln, i) => `<text x="${x + 12}" y="${ty + i * 17}" class="n-t">${esc(ln)}</text>`).join("")}
    ${sub ? `<text x="${x + 12}" y="${y + h - 10}" class="n-s">${esc(sub.length > Math.floor((w - 20) / 6.2) ? sub.slice(0, Math.floor((w - 20) / 6.2) - 1) + "…" : sub)}</text>` : ""}</g>`;
}

/* What each frontend ships as, for the diagram (not every frontend is "static assets + CDN"). */
const FE_SHIPS = { nextjs: "server rendering + CDN", nuxt: "server rendering + CDN", sveltekit: "server rendering + CDN",
  astro: "static build + CDN", react_spa: "static build + CDN", angular: "static build + CDN", htmx: "HTML rendered by the backend",
  react_native: "iOS + Android app", flutter: "iOS + Android app", native_mobile: "iOS + Android apps" };
const BAAS = ["supabase", "firebase"];

function archSvg(narrow) {
  const r = S.result, st = r.stack, pr = r.profile || {};
  const plats = (pr.platforms || ["web"]).map((p) => ({ web: "Web", ios: "iOS", android: "Android" }[p] || p)).join(" · ");
  const client = r.companion ? `${plats} · ${short(r.companion.name)}` : plats;
  const off = st.database.managed_offering ? short(st.database.managed_offering) : "self-managed";
  const api = st.hosting.api_host;
  const baas = BAAS.includes(st.backend.pick.id), provided = !!st.hosting.optional_host;
  const host = short(st.hosting.pick.name) + (api ? ` + API on ${short(api.name)}` : "");
  const feSub = FE_SHIPS[st.frontend.pick.id] || "static assets + CDN";
  const beId = st.backend.pick.id;
  const beSub = api ? `on ${short(api.name)}` : baas ? `managed by ${short(st.backend.pick.name)}` : beId === "serverless_functions" ? "functions, per request"
    : beId === "no_custom_backend" ? "none: pages are files" : r.architecture.style;
  /* A secondary store serving several shapes is one service, e.g. "Secondary store (graph, vector)". */
  const side = SIDE_ROLES.map((role) => r.supporting_services.find((s) => s.role === role
    || (role === "Secondary store (graph)" && /^Secondary store \(.*graph/.test(s.role)))).filter(Boolean).slice(0, 3);
  const arrow = (d) => `<path d="${d}" class="e" marker-end="url(#ah)"/>`;
  const defs = `<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="ah"/></marker></defs>`;
  const label = `Architecture: users on ${plats} reach ${st.frontend.pick.name}${provided ? " from the app stores" : `, served from ${st.hosting.pick.name}`}, which calls ${st.backend.pick.name}${api ? ` on ${api.name}` : baas ? ", a hosted backend outside your own hosting" : ""}, which stores data in ${st.database.pick.name}${side.length ? `, with ${side.map((s) => s.role.toLowerCase()).join(", ")}` : ""}.`;
  if (!narrow) {
    const W = 860, H = side.length ? 300 : 186;
    const sideW = side.length ? Math.min(140, (436 - (side.length - 1) * 10) / side.length) : 0;
    /* The hosting zone holds only what runs on your host: a BaaS backend sits outside it, and a mobile-only app has none. */
    const zone = provided ? "" : `<rect x="170" y="14" width="${baas ? 220 : 456}" height="${baas ? 150 : H - 28}" rx="14" class="zone"/>
      <text x="186" y="34" class="z-t">Hosting · ${esc(((h, n) => (h.length > n ? h.slice(0, n - 1) + "…" : h))(baas ? short(st.hosting.pick.name) : host, baas ? 18 : 50))}</text>`;
    return `<svg class="arch" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">${defs}${zone}
      ${node(10, 62, 130, 84, "Users", "Clients", client)}
      ${node(186, 62, 190, 84, provided ? "App" : "Frontend", st.frontend.pick.name, feSub)}
      ${node(420, 62, 190, 84, baas ? "Backend (hosted service)" : "Backend / API", st.backend.pick.name, beSub, baas ? "baas" : "")}
      ${node(664, 62, 186, 84, "Database", st.database.pick.name, off, "db")}
      ${arrow("M140 104H182")}${arrow("M376 104H416")}${arrow("M610 104H660")}
      ${side.map((s, i) => { const x = 186 + i * (sideW + 10); return arrow(`M515 146V166H${x + sideW / 2}V196`) + node(x, 200, sideW, 64, s.role, s.name.split(/\s*[/(]/)[0], "", "side"); }).join("")}
    </svg>`;
  }
  const W = 340, x = 20, w = 300;
  let y = 10, parts = [], zoneEnd = null;
  parts.push(node(x, y, w, 70, "Users", "Clients", client)); y += 70;
  parts.push(arrow(`M170 ${y}V${y + 24}`)); y += 28;
  const zoneTop = y;
  if (!provided) y += 30;
  parts.push(node(x + 12, y, w - 24, 70, provided ? "App" : "Frontend", st.frontend.pick.name, feSub)); y += 70;
  if (baas) { y += 12; zoneEnd = y; }
  parts.push(arrow(`M170 ${y}V${y + 20}`)); y += 24;
  parts.push(node(x + 12, y, w - 24, 70, baas ? "Backend (hosted service)" : "Backend / API", st.backend.pick.name, beSub, baas ? "baas" : "")); y += 70;
  side.forEach((s) => { parts.push(arrow(`M60 ${y}V${y + 18}`)); y += 22; parts.push(node(x + 30, y, w - 54, 54, s.role, s.name.split(/\s*[/(]/)[0], "", "side")); y += 54; });
  y += 12;
  if (zoneEnd === null) zoneEnd = y;
  const hname = baas ? short(st.hosting.pick.name) : host;
  const zone = provided ? "" : `<rect x="${x}" y="${zoneTop}" width="${w}" height="${zoneEnd - zoneTop}" rx="14" class="zone"/><text x="${x + 14}" y="${zoneTop + 20}" class="z-t">Hosting · ${esc(hname.length > 30 ? hname.slice(0, 29) + "…" : hname)}</text>`;
  parts.push(arrow(`M170 ${y}V${y + 24}`)); y += 28;
  parts.push(node(x, y, w, 70, "Database", st.database.pick.name, off, "db")); y += 80;
  return `<svg class="arch narrow" viewBox="0 0 ${W} ${y}" role="img" aria-label="${esc(label)}">${defs}${zone}${parts.join("")}</svg>`;
}

function archPanel() {
  const r = S.result;
  return `<div class="arch-wrap">${archSvg(false)}${archSvg(true)}</div>
    <p class="small"><b>${esc(r.architecture.style)}.</b> ${esc(r.architecture.why)}</p>
    <p class="muted small"><b>Availability:</b> ${esc(r.architecture.redundancy)}</p>
    ${(r.architecture.how_parts_fit || []).length ? `<h4>How the parts fit</h4><ol class="fit">${r.architecture.how_parts_fit.map((s) => `<li><b>${esc(s.step)}.</b> ${esc(s.text)}</li>`).join("")}</ol>` : ""}
    <ul class="services">${r.supporting_services.map((s) => `<li><span class="sv-r">${esc(s.role)}</span><b>${esc(s.name)}</b><span class="muted">${esc(s.why)}</span></li>`).join("")}</ul>
    ${deferredPanel(r)}`;
}

function deferredPanel(r) {
  const later = r.deferred_services || [];
  if (!later.length) return "";
  const ob = r.ops_budget;
  return `<h4 class="small">Add later (ops budget: ${ob.cap} extra system${ob.cap === 1 ? "" : "s"} for a team of ${ob.team_size})</h4>
    <p class="muted small">${esc(ob.note)}</p>
    <ul class="services">${later.map((s) => `<li><span class="sv-r">${esc(s.role)}</span><b>${esc(s.name)}</b><span class="muted">Add ${esc(s.trigger)}.</span></li>`).join("")}</ul>`;
}

/* ================================================================== knowledge base */
async function renderKb() {
  const el = $("#view-kb");
  el.innerHTML = skeleton();
  let kb;
  try { kb = await api("/api/kb"); } catch (e) {
    el.innerHTML = `<div class="empty" role="alert"><h2>Could not load the knowledge base</h2><p>${esc(e.message)}</p></div>`; return;
  }
  const crit = { frontend: ["ease", "ops", "maturity", "realtime", "performance", "seo", "velocity", "hiring", "offline", "structure", "interactivity"],
    backend: ["scalability", "ease", "ops", "maturity", "realtime", "performance", "velocity", "hiring", "structure"],
    database: ["scalability", "ease", "ops", "maturity", "realtime", "performance", "hiring", "offline"],
    hosting: ["scalability", "ease", "ops", "maturity", "realtime", "performance"] };
  const total = LAYERS.map((l) => kb[l].length).reduce((a, b) => a + b);
  el.innerHTML = `<div class="kb-head"><h1>${total} technologies. ${kb.rules.length} compatibility rules. Every technology cites its sources; scores follow a 1–5 rubric.</h1>
    <p class="lead">Scores run 1–5 (5 = best; “ease” = gentle learning curve, “ops” = low operational burden). Each row links to the documentation it came from.</p></div>` +
    LAYERS.map((l) => `<section class="kb-sec" aria-labelledby="kb-${l}"><h2 id="kb-${l}">${cap(l)} <small>${kb[l].length} options</small></h2>
    <div class="table-wrap"><table class="tbl kb">
    <thead><tr><th scope="col">Technology</th>${crit[l].map((c) => `<th scope="col" class="num">${c}</th>`).join("")}${l === "database" ? '<th scope="col">consistency</th>' : ""}${l === "hosting" ? '<th scope="col">regions</th><th scope="col">HIPAA / PCI</th>' : ""}<th scope="col" class="num">lock-in</th><th scope="col">sources</th></tr></thead>
    <tbody>${kb[l].map((t) => `<tr><th scope="row"><b>${esc(t.name)}</b><span class="muted">${esc(t.summary)}</span></th>${crit[l].map((c) => `<td class="num heat" style="--h:${((t.scores[c] ?? 0) / 5).toFixed(2)}"><span class="mono">${t.scores[c] ?? "-"}</span></td>`).join("")}
      ${l === "database" ? `<td>${esc(t.consistency)}</td>` : ""}${l === "hosting" ? `<td class="small">${esc((t.regions || []).join(", "))}</td><td>${t.compliance.hipaa ? "BAA" : "-"} / ${t.compliance.pci ? "yes" : "-"}</td>` : ""}
      <td class="num mono">${t.lock_in ?? "-"}</td><td class="srcs">${t.sources.map((s, i) => `<a href="${esc(s)}" target="_blank" rel="noopener" aria-label="${esc(t.name)} source ${i + 1}">[${i + 1}]</a>`).join(" ")}</td></tr>`).join("")}</tbody></table></div></section>`).join("");
}

/* ================================================================== glossary popover (one shared, keyboard + touch friendly) */
function openTerm(btn) {
  const pop = $("#gpop");
  if (S.popBtn === btn && !pop.hidden) { closeTerm(true); return; }
  closeTerm(false);
  const terms = btn.dataset.terms.split(",").map((t) => S.glossary.terms[t]).filter(Boolean);
  if (!terms.length) return;
  pop.innerHTML = `<button type="button" class="gp-x" aria-label="Close">${ICON.close}</button>` + terms.map((g, i) => `<section${i ? ' class="gp-more"' : ""}>
      <h3 id="gp-h${i}">${esc(g.term)}</h3><p>${esc(g.definition)}</p>
      <p class="gp-a"><b>Who it applies to:</b> ${esc(g.applies)}</p>
      <p class="gp-s"><a href="${esc(g.source)}" target="_blank" rel="noopener">${ICON.ext}<span>Source: ${esc(g.source_name || g.source)}</span></a></p></section>`).join("");
  pop.setAttribute("aria-labelledby", "gp-h0");
  pop.hidden = false;
  btn.setAttribute("aria-expanded", "true");
  S.popBtn = btn;
  placeTerm();
  pop.focus({ preventScroll: true });
}

function placeTerm() {
  const pop = $("#gpop"), btn = S.popBtn;
  if (!btn || pop.hidden) return;
  const r = btn.getBoundingClientRect(), vw = document.documentElement.clientWidth;
  const w = Math.min(340, vw - 32);
  pop.style.width = `${w}px`;
  const left = Math.max(16, Math.min(r.left + r.width / 2 - w / 2, vw - 16 - w));
  const h = pop.offsetHeight;
  const below = r.bottom + 8 + h <= innerHeight || r.top < h + 8;
  pop.style.left = `${left + scrollX}px`;
  pop.style.top = `${(below ? r.bottom + 8 : r.top - h - 8) + scrollY}px`;
}

function closeTerm(focusBack = true) {
  const pop = $("#gpop");
  if (!pop || pop.hidden) return;
  pop.hidden = true;
  const b = S.popBtn; S.popBtn = null;
  if (b) { b.setAttribute("aria-expanded", "false"); if (focusBack && b.isConnected) b.focus(); }
}

/* ================================================================== views, helpers, boot */
const slug = () => String(S.answers.project_name || "stack").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "stack";
function download(name, text, type) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function show(view) {
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  $$(".nav-b").forEach((t) => (t.dataset.view === view ? t.setAttribute("aria-current", "page") : t.removeAttribute("aria-current")));
  if (view === "kb" && !$("#view-kb").innerHTML) renderKb();
  $("#sumbar")?.classList.toggle("off", view !== "app");
  window.scrollTo(0, 0);
}

function editField(k) {
  const i = stepOfField(k);
  if (i < 0) return;
  show("app");
  toggleRefine(true);
  const g = $(`#form details[data-step="${i}"]`); if (g) g.open = true;
  const f = $(`#f-${k}`);
  if (f) {
    f.scrollIntoView({ behavior: "auto", block: "center" });
    f.classList.add("flash"); setTimeout(() => f.classList.remove("flash"), 1600);
    const inp = $("input", f); if (inp) inp.focus({ preventScroll: true });
  }
}

/* Print: every drawer, layer and collapsed section is shown so the report is complete. */
let reopened = [];
addEventListener("beforeprint", () => { reopened = $$("#out details:not([open])"); reopened.forEach((d) => (d.open = true)); });
addEventListener("afterprint", () => { reopened.forEach((d) => (d.open = false)); reopened = []; });

/* Re-draw nothing on resize: both diagram layouts are in the DOM and CSS picks one. */
addEventListener("resize", () => { stickyOffset(); closeTerm(false); });

const wait = (ms) => new Promise((res) => setTimeout(res, ms));
async function settled() { /* deep links: wait for the debounce, the live run and the sensitivity call */
  for (let i = 0; i < 80 && (S.timer && S.pending || S.ctl || S.sensCtl); i++) await wait(50);
  await wait(60);
}

(async function boot() {
  initTheme();
  try {
    [S.questions, S.presets] = await Promise.all([api("/api/questions"), api("/api/presets")]);
  } catch (e) {
    $("#out").innerHTML = `<div class="empty" role="alert"><h2>Could not load the questions</h2><p>${esc(e.message)} Start the server with <code>python run.py</code> and reload.</p></div>`;
    return;
  }
  try { S.glossary = await api("/api/glossary"); } catch (e) { S.glossary = null; /* (i) buttons are simply omitted */ }
  S.answers = defaults();
  $("#n-q").textContent = allFields().length;
  api("/api/health").then((h) => {
    S.health = h;
    $("#n-tech").textContent = Object.values(h.technologies).reduce((a, b) => a + b, 0);
    $("#n-rules").textContent = h.rules;
    setLlmNote({ enabled: !!h.llm_enabled });
    renderSecond();
  }).catch(() => {});
  renderExamples(); renderQuick(); bindRefine();

  $("#quick").addEventListener("change", onQuickChange);
  $("#asknext-btn").onclick = askNext;
  $("#brief-btn").onclick = fillFromBrief;
  $("#refine-toggle").onclick = () => toggleRefine();
  $("#reset").onclick = () => {
    const before = S.answers;
    S.answers = defaults(); S.unknown.clear(); S.touched.clear(); S.briefSrc = {};
    renderRefine(); syncQuick(); syncSliders(); updateCounts();
    queueRun(Object.keys(before), before);
  };
  $$(".nav-b").forEach((t) => (t.onclick = () => show(t.dataset.view)));
  $("#sumbar-btn").onclick = () => { $("#out").scrollIntoView({ behavior: smooth(), block: "start" }); $("#res-title")?.focus({ preventScroll: true }); };
  document.addEventListener("click", (e) => {
    const gi = e.target.closest(".gi");
    if (gi) { e.preventDefault(); openTerm(gi); return; }
    if (e.target.closest(".gp-x")) { closeTerm(true); return; }
    if (!e.target.closest("#gpop")) closeTerm(false);
    const go = e.target.closest("[data-go]");
    if (go) { e.preventDefault(); show(go.dataset.go); return; }
    const ed = e.target.closest("[data-edit]");
    if (ed) { editField(ed.dataset.edit); return; }
    const pt = e.target.closest(".pick-this");
    if (pt) { onPickThis(pt); return; }
    const hb = e.target.closest("[data-hint]");
    if (hb) { const box = $(`#hint-${hb.dataset.hint}`), open = box.hidden; box.hidden = !open; hb.setAttribute("aria-expanded", String(open)); return; }
    const op = e.target.closest("[data-open]");
    if (op) { openPanel(op.dataset.open, { layer: op.dataset.layer || null, focus: !op.classList.contains("drawer-b") }); return; }
    if (e.target.closest("#rob-go")) { runRobustness(); return; }
    if (e.target.closest("#sum-go")) { loadSummary(); return; }
    if (e.target.closest("#second-go")) { loadSecond(); return; }
    const wn = e.target.closest("[data-whynot]");
    if (wn) { runWhyNot(wn.dataset.whynot); return; }
    const wl = e.target.closest("[data-why-layer]");
    if (wl) selectWhy(wl.dataset.whyLayer);
  });
  document.addEventListener("keydown", (e) => {
    const pop = $("#gpop");
    if (e.key === "Escape" && !pop.hidden) { e.preventDefault(); closeTerm(true); return; }
    if (e.key === "Tab" && !pop.hidden && pop.contains(document.activeElement)) { /* keep focus inside the open popover */
      const f = $$("a, button", pop), first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === pop)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      return;
    }
    /* Arrow keys move between layer tabs in the "Why" drawer. */
    const t = e.target.closest && e.target.closest("[data-why-layer]");
    if (!t || !["ArrowLeft", "ArrowRight"].includes(e.key)) return;
    const i = LAYERS.indexOf(t.dataset.whyLayer), n = LAYERS[(i + (e.key === "ArrowRight" ? 1 : 3)) % 4];
    selectWhy(n); $(`[data-why-layer="${n}"]`).focus();
  });

  /* Desktop sticky offset follows the result's height; the mobile bar hides while the full result is on screen. */
  if ("ResizeObserver" in window) new ResizeObserver(stickyOffset).observe($("#out"));
  if ("IntersectionObserver" in window) {
    new IntersectionObserver((es) => es.forEach((x) => $("#sumbar").classList.toggle("away", x.isIntersecting)), { threshold: 0.15 }).observe($("#out"));
  }

  /* Deep links for demos and screenshots:
     #a=<shared answers, from "Copy link">&preset=<id>&whatif=<key>:<value>&unsure=<k1,k2>&term=<glossary id>&panel=<why|growth|arch|cost|alts|inputs>
     &layer=<layer>&refine=1&open=<step index>&at=<element id>&view=kb&whynot=<layer>:<id> */
  const h = new URLSearchParams(location.hash.slice(1));
  if (h.get("view") === "kb") { show("kb"); return; }
  if (h.get("refine")) toggleRefine(true);
  if (h.get("open")) h.get("open").split(",").forEach((i) => { const g = $(`#form details[data-step="${i}"]`); if (g) g.open = true; });
  const shared = h.get("a") ? Share.decode(h.get("a")) : null;
  if (shared) {
    const known = Object.fromEntries(Object.entries(shared.answers).filter(([k]) => fieldByKey(k)));
    await loadProject(known, shared.unknown.filter((k) => fieldByKey(k)));
  } else if (h.get("preset")) await runPreset(h.get("preset"));
  else await run({ compare: false }); /* an immediate result from the defaults */
  const un = (h.get("unsure") || "").split(",").filter((k) => fieldByKey(k));
  un.forEach((k) => { S.unknown.add(k); S.answers[k] = structuredClone(fieldByKey(k).default); });
  if (un.length) { syncQuick(); syncSliders(); if ($("#form").innerHTML) renderRefine(); updateCounts(); await run(); }
  const wi = h.get("whatif");
  if (wi) {
    const [k, v] = wi.split(":");
    if (fieldByKey(k)) { const old = S.answers[k]; S.answers[k] = +v; commit([k], { [k]: old }); }
  }
  await settled();
  const wn = (h.get("whynot") || "").split(":");
  if (wn.length === 2 && LAYERS.includes(wn[0])) {
    openPanel("why", { layer: wn[0] });
    const sel = $(`[data-wn-sel="${wn[0]}"]`);
    if (sel) { sel.value = wn[1]; await runWhyNot(wn[0]); }
  }
  if (h.get("panel")) { openPanel(h.get("panel"), { layer: h.get("layer") }); if (h.get("panel") === "growth") { await wait(400); await settled(); } }
  if (h.get("at")) document.getElementById(h.get("at"))?.scrollIntoView({ block: "start" });
  if (h.get("y")) scrollTo(0, +h.get("y"));
  if (h.get("term")) { const b = $(`.gi[data-terms^="${h.get("term")}"]`); if (b) { b.scrollIntoView({ block: "center" }); openTerm(b); } }
})();
