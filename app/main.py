"""FastAPI server: JSON API for the engine plus the single-page frontend."""
from __future__ import annotations

import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from engine import __version__, llm, parallel, recommend
from engine.brief import MAX_BRIEF_CHARS, parse_brief
from engine.export import to_adr, to_markdown
from engine.kb import LAYERS, load_glossary, load_kb, load_presets, load_questions, validate_kb
from engine.recommender import switch_reasons
from engine.robustness import robustness
from engine.sensitivity import next_questions, sensitivity
from engine.standard import FIELD_HELP, FIELDS, PRIORITY_KEYS, run_text
from engine.summary import summarize
from engine.whatif import MAX_QUESTION_CHARS, propose_changes
from engine.whynot import why_not

STATIC = Path(__file__).resolve().parent / "static"
# Example scenario files: the six public ones from the problem statement, then the edge cases written for the report.
EXAMPLES = {"public": Path(__file__).resolve().parent.parent / "scenarios" / "public",
            "edge": Path(__file__).resolve().parent.parent / "scenarios" / "edge"}
MAX_BODY_BYTES = 256 * 1024  # the largest legitimate request is a few KB of answers
FREE_TEXT_LISTS = {"team_skills"}  # these multiselects also accept free text, so their items are not restricted to the listed options


def answers_schema() -> dict:
    """JSON Schema for the answers object, written from data/questions.json so /docs and the form cannot disagree."""
    props: dict[str, dict] = {}
    for step in load_questions()["steps"]:
        for f in step["fields"]:
            s: dict = {"title": f["label"], "description": f["help"]}
            if f["type"] == "number":
                s["type"] = "number"
                if f.get("min") is not None:
                    s["minimum"] = f["min"]
                if f.get("max") is not None:
                    s["maximum"] = f["max"]
            elif f["type"] == "select":
                s.update(type="string", enum=[o["value"] for o in f["options"]])
            elif f["type"] == "multiselect":
                items: dict = {"type": "string"}
                if f["key"] not in FREE_TEXT_LISTS:
                    items["enum"] = [o["value"] for o in f["options"]]
                s.update(type="array", items=items)
            elif f["type"] == "bool":
                s["type"] = "boolean"
            else:
                s["type"] = "string"
            if f.get("default") is not None:
                s["default"] = f["default"]
            props[f["key"]] = s
    return {"type": "object", "properties": props, "additionalProperties": True,
            "description": "Any subset of the answers; every missing one takes its documented default and is listed under 'Defaults used'."}


def _examples() -> dict:
    out = {"minimal": {"summary": "Only a few answers", "value": {"app_type": "saas", "dau": 5000, "budget_monthly": 200, "team_size": 3}}}
    for p in load_presets():
        if p["id"] in ("startup_mvp", "hipaa_telehealth", "india_ecommerce_scale"):
            out[p["id"]] = {"summary": p["name"], "value": p["input"]}
    return out


def answers_body():
    """Request body that is the answers object itself."""
    return Body(default_factory=dict, json_schema_extra=answers_schema(), openapi_examples=_examples())


def wrapped_body(description: str, **properties: dict):
    """Request body that holds the answers (or two answer sets) inside a wrapper object."""
    return Body(default_factory=dict, json_schema_extra={"type": "object", "description": description, "properties": properties})


_ANSWERS_REF = {"type": "object", "description": "Answers: any subset of the properties listed under POST /api/recommend."}

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start the worker processes for the 'Ask next' card in the background, so the first request does not wait for them."""
    threading.Thread(target=parallel.get_pool, daemon=True).start()
    yield
    parallel.shutdown()


app = FastAPI(lifespan=lifespan, title="StackSense", version=__version__,
              description="Deterministic, explainable tech-stack recommendation engine: the rules make every decision, so the same answers always "
                          "give the same stack. POST any subset of the answers (the schema is written from data/questions.json) and read "
                          "the stack, the reasons, the cost and the warnings back. The /api/brief, /api/summary and /api/whatif "
                          "endpoints optionally use a language model to read free text and word summaries; they work without a key.")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    """Reject API requests that declare a body larger than MAX_BODY_BYTES (413) before reading it."""
    # shortcut: trusts the Content-Length header; a chunked upload without one is not capped here (put a proxy limit in front).
    declared = request.headers.get("content-length", "")
    if request.url.path.startswith("/api/") and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return JSONResponse({"detail": f"Request body is larger than {MAX_BODY_BYTES // 1024} KB"}, status_code=413)
    return await call_next(request)

_problems = validate_kb()
if _problems:  # fail fast on a broken knowledge base
    raise RuntimeError("Knowledge base invalid: " + "; ".join(_problems[:5]))


@app.get("/", include_in_schema=False)
def index():
    """Serve the single-page web UI."""
    return FileResponse(STATIC / "index.html")


@app.get("/scenario", include_in_schema=False)
def scenario_page():
    """Serve the scenario-file page: the standard input schema as a form, import and export of JSON."""
    return FileResponse(STATIC / "scenario.html")


@app.get("/api/health", summary="Status and knowledge-base counts", tags=["data"])
def health():
    """Returns status ok with the version, the number of technologies per layer, the number of rules, whether an LLM key is
    configured (llm_enabled) and whether the LLM-off switch STACKSENSE_LLM=off is set (llm_switched_off)."""
    kb = load_kb()
    return {"status": "ok", "version": __version__,
            "technologies": {l: len(kb[l]) for l in LAYERS}, "rules": len(kb["rules"]), "llm_enabled": llm.available(),
            "llm_switched_off": llm.switched_off()}


@app.get("/api/scenario/fields", summary="The standard scenario schema (problem statement section 3.1)", tags=["scenario"])
def scenario_fields():
    """Every field of the standard input schema: path, kind, whether it is required, its default, allowed values and meaning.
    The scenario page builds its form from this list."""
    out = [{"path": path, "kind": kind, "required": req, "default": default, "allowed": list(allowed or []),
            "help": FIELD_HELP.get(path, "")} for path, kind, req, default, allowed in FIELDS]
    return out + [{"path": f"priorities.{k}", "kind": "priority", "required": False, "default": 3, "allowed": [1, 2, 3, 4, 5],
                   "help": "1 (low) to 5 (high)"} for k in PRIORITY_KEYS]


def _example_files() -> dict[str, tuple[str, Path]]:
    return {f.stem: (group, f) for group, folder in EXAMPLES.items() for f in sorted(folder.glob("*.json"))}


@app.get("/api/scenario/examples", summary="The example scenario files in scenarios/public and scenarios/edge", tags=["scenario"])
def scenario_examples():
    """The example scenario files by name, each with its group (public or edge) and project name. Their outputs are
    computed when run, never stored."""
    out = []
    for stem, (group, f) in _example_files().items():
        try:
            name = (json.loads(f.read_text(encoding="utf-8")).get("project") or {}).get("name")
        except (OSError, ValueError, AttributeError):
            name = None
        out.append({"name": stem, "group": group, "project": name})
    return out


@app.get("/api/scenario/examples/{name}", summary="One example scenario file", tags=["scenario"])
def scenario_example(name: str):
    """The scenario file scenarios/public/<name>.json or scenarios/edge/<name>.json as it is on disk."""
    files = {stem: f for stem, (_group, f) in _example_files().items()}
    if name not in files:
        raise HTTPException(status_code=404, detail=f"No example named {name!r}")
    return json.loads(files[name].read_text(encoding="utf-8"))


@app.post("/api/scenario", summary="Run a scenario file in the standard schema", tags=["scenario"],
          openapi_extra={"requestBody": {"required": True, "content": {"application/json": {"schema": {
              "type": ["object", "array"], "description": "A scenario in the standard schema (problem statement section 3.2), "
                                                         "or a JSON array of scenarios."}}}}})
async def api_scenario(request: Request):
    """Body: the scenario JSON. Returns the problem statement's section 4 output: status, summary, architecture_style, stack
    (frontend, backend, database, hosting, supporting), estimated_monthly_cost_usd, warnings, assumptions and
    validation_errors. A JSON array of scenarios returns an array with one output per element. Invalid input gives
    status invalid_input with field-level errors, not an HTTP error. No language model is involved, so the result is
    the same with the LLM-off switch set."""
    text = (await request.body()).decode("utf-8-sig", errors="replace")
    return await run_in_threadpool(run_text, text)  # the engine is CPU work: keep it off the event loop


@app.get("/api/questions", summary="The questionnaire (input schema)", tags=["data"])
def questions():
    """Every question with its type, default, range, options, help text, 'why we ask' note and sources. The form is rendered from this."""
    return load_questions()


@app.get("/api/presets", summary="Ready-made example projects", tags=["data"])
def presets():
    """The built-in example projects, each with the answers that define it."""
    return load_presets()


@app.get("/api/glossary", summary="Plain-English definitions of technical terms", tags=["data"])
def glossary():
    """Definitions, who each term applies to, and an official source."""
    return load_glossary()


@app.get("/api/kb", summary="The knowledge base", tags=["data"])
def knowledge_base():
    """All technologies per layer with their scores, costs and sources, plus the compatibility rules."""
    kb = load_kb()
    return {l: kb[l] for l in LAYERS} | {"rules": kb["rules"]}


@app.post("/api/recommend", summary="Recommend a stack", tags=["engine"])
def api_recommend(payload: dict = answers_body(), lite: bool = False):
    """Body: any subset of the answers. Returns the explained recommendation: the pick per layer with score, reasons,
    trade-offs, risks, the answers that moved the score, the runner-up, alternatives and exclusions, the architecture,
    supporting services, a cost estimate, warnings and counterfactuals. `lite=true` skips the counterfactual re-runs
    (used by the UI's growth path, which only needs the picks)."""
    return recommend(payload, with_counterfactuals=not lite)


@app.post("/api/sensitivity", summary="What depends on an answer you are not sure about", tags=["engine"])
def api_sensitivity(payload: dict = wrapped_body(
        'Body: {"answers": {...}, "unknown": ["dau"]}.', answers=_ANSWERS_REF,
        unknown={"type": "array", "items": {"type": "string"}, "description": 'Question keys the user is not sure about, for example ["dau"].'})):
    """Body: {"answers": {...}, "unknown": ["dau", ...]}. For each unknown answer, reports per layer
    whether the pick is robust across that answer's plausible values or which value flips it."""
    answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
    unknown = payload.get("unknown") if isinstance(payload.get("unknown"), list) else []
    return sensitivity(answers, [str(k) for k in unknown])


@app.post("/api/next", summary="Which unanswered questions can still change a pick", tags=["engine"])
def api_next(payload: dict = wrapped_body('Body: {"answers": {...}} with only the answers the user gave.', answers=_ANSWERS_REF)):
    """Body: {"answers": {...}} (only the answers the user gave). Ranks the unanswered questions by the
    layers they can still change."""
    answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
    return next_questions(answers, parallel.get_pool())


@app.post("/api/switch", summary="Why a pick changed between two answer sets", tags=["engine"])
def api_switch(payload: dict = wrapped_body('Body: {"before": {...answers}, "after": {...answers}}.', before=_ANSWERS_REF, after=_ANSWERS_REF)):
    """Body: {"before": {...answers}, "after": {...answers}}. For each layer whose pick differs, the
    cause of the switch: an exclusion, the criterion or penalty that moved the gap, or a stack rule."""
    before = payload.get("before") if isinstance(payload.get("before"), dict) else {}
    after = payload.get("after") if isinstance(payload.get("after"), dict) else {}
    return switch_reasons(before, after)


@app.post("/api/whynot", summary="Why not this option, or this whole stack", tags=["engine"])
def api_whynot(payload: dict = wrapped_body(
        'Body: {"answers": {...}, "pins": {"hosting": "netlify"}}.', answers=_ANSWERS_REF,
        pins={"type": "object", "additionalProperties": {"type": "string"},
              "description": 'Layer to technology id, for example {"hosting": "netlify"}; give all four layers to grade a whole stack.'})):
    """Body: {"answers": {...}, "pins": {"hosting": "netlify"}} (one layer, or all four to grade a stack).
    Returns the gap to the recommendation, the criteria, rules and cost behind it, any exclusion, and
    the single answer changes that would make the named choice the pick."""
    answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
    pins = payload.get("pins") if isinstance(payload.get("pins"), dict) else {}
    return why_not(answers, {str(k): str(v) for k, v in pins.items()})


@app.post("/api/robustness", summary="How stable each pick is under score noise", tags=["engine"])
def api_robustness(payload: dict = answers_body()):
    """Body: answers. Re-runs the engine 30 times per noise level with every knowledge-base score shifted
    by seeded random noise (+/-0.25, +/-0.5) and reports how often each layer keeps its pick."""
    return robustness(payload)


@app.post("/api/export/markdown", response_class=PlainTextResponse, summary="Markdown report", tags=["export"])
def api_markdown(payload: dict = answers_body()):
    """Body: answers. Returns the recommendation as a Markdown document."""
    return PlainTextResponse(to_markdown(recommend(payload)), media_type="text/markdown; charset=utf-8")


@app.post("/api/export/adr", response_class=PlainTextResponse, summary="Architecture decision records", tags=["export"])
def api_adr(payload: dict = answers_body()):
    """Body: answers. Returns one architecture decision record per layer (context, decision, alternatives considered,
    consequences, when to revisit) as Markdown."""
    return PlainTextResponse(to_adr(recommend(payload)), media_type="text/markdown; charset=utf-8")


def _text_field(payload: dict, key: str, limit: int) -> str:
    """A required, non-empty string from the request body, at most `limit` characters long."""
    text = payload.get(key)
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=422, detail=f"'{key}' must be a non-empty string")
    if len(text) > limit:
        raise HTTPException(status_code=422, detail=f"'{key}' is longer than {limit} characters")
    return text


@app.post("/api/brief", summary="Fill the questionnaire from a project description", tags=["llm"])
def api_brief(payload: dict = wrapped_body('Body: {"text": "We are 3 students building a fest ticketing site for about 20,000 users a day..."}',
                                           text={"type": "string", "maxLength": MAX_BRIEF_CHARS,
                                                 "description": "Free-text project description."})):
    """Body: {"text": "..."}. Reads the description with patterns (always) and with a language model (only when an API key is
    set, and only for questions the patterns left open). Returns, per answered question, the value, its source ("rule" or
    "llm") and the words of the description it came from, plus the questions still unknown. A model value is kept only if it
    is valid for the question and its quote occurs in the text."""
    return parse_brief(_text_field(payload, "text", MAX_BRIEF_CHARS))


@app.post("/api/summary", summary="Plain-English summary of the recommendation", tags=["llm"])
def api_summary(payload: dict = answers_body()):
    """Body: answers (same as /api/recommend). Runs the engine, then asks a language model to re-word the engine's own facts as a
    short summary per layer plus an overall paragraph. The text is accepted only if every technology name and number in it appears
    in the facts; after one retry it falls back to the engine's template explanation. Without an API key the template is returned.
    "source" says which one you got and "checked" is true only for checked model text."""
    return summarize(recommend(payload, with_counterfactuals=False))


@app.post("/api/whatif", summary="Map a plain-English what-if question to answer changes", tags=["engine"])
def api_whatif(payload: dict = wrapped_body(
        'Body: {"answers": {...}, "question": "What if we had ten times the users?"}.', answers=_ANSWERS_REF,
        question={"type": "string", "maxLength": MAX_QUESTION_CHARS, "description": "The what-if question."})):
    """Body: {"answers": {...}, "question": "..."}. Maps the question to changes of the answers with the pattern reader only:
    the problem statement allows a language model to read the project description, not other text. Each change is checked
    against the questionnaire and must quote the question. Returns the changes with their previous values; re-run
    /api/recommend with the changed answers to see the effect."""
    answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
    return propose_changes(_text_field(payload, "question", MAX_QUESTION_CHARS), answers, use_llm=False)

