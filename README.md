# StackSense

An explainable tech-stack recommendation engine for the Synergy '26 StackSense Challenge, by Kanav Bhardwaj (IIIT Bangalore). Repository: <https://github.com/Paradox-73/StackSense26>

StackSense takes a software project's parameters (scale, team and skills, budget, timeline, infrastructure, compliance, priorities) and recommends a frontend, backend, database and hosting platform, plus supporting services such as a cache, a job queue, sign-in, storage, a CDN or payments when the inputs call for them. It reads scenario files in the challenge's standard input schema and writes the standard output schema. Every choice comes from rules and weighted scoring over a cited knowledge base of 64 technologies, never from a language model, so the same input always gives the same stack. Each component lists the input fields that drove it, at least one alternative with the reason it lost, its trade-offs and a monthly cost band; contradictions and broken constraints come back as warnings with a severity.

![StackSense architecture: the entry points, the FastAPI app, the scenario adapter, the pure-Python rule engine and its data files, and the optional language-model layer with its checks and off switch](docs/architecture.svg)

## System architecture

```
 scenario JSON (standard schema)          web questionnaire (42 questions)
   cli.py --scenario, POST /api/scenario    app/static/index.html, POST /api/recommend
            |                                         |
            v                                         |
 engine/standard.py: check every field -> validation_errors (status invalid_input, stack null)
            | map fields to engine answers; every default and reading goes to assumptions
            v                                         v
 engine/profile.py   clean answers, derive numbers (requests/s, data size, scale tier)
 engine/conflicts.py contradictions -> warnings with severity (info, warning, critical)
 engine/scoring.py   weights per criterion from the answers; hard constraints remove options
 engine/recommender.py  score each option, search 625 stack combinations, apply compatibility rules
 engine/advice.py    architecture style, supporting services, monthly cost band
 engine/explain.py   reasons, driven-by inputs, runner-up, alternatives, trade-offs
            |                                         |
            v                                         v
 section 4 output JSON (status, stack, cost, warnings,     the app's result page (scores, why, what if)
 assumptions, validation_errors) -> outputs/<id>_output.json
```

| Module | Where | What it does |
|---|---|---|
| Web UI | `app/static/` | Plain HTML, CSS and JavaScript, no build step. `index.html` is the guided questionnaire; `scenario.html` (at `/scenario`) is a form with every field of the standard schema, import of a scenario JSON and export of the output JSON. |
| API | `app/main.py` | FastAPI routes: `POST /api/scenario` (standard schema in, standard output out), `POST /api/recommend` and the analysis routes for the questionnaire. Interactive docs at `/docs`. |
| Scenario adapter | `engine/standard.py` | Validates a scenario file field by field, maps it to the engine's answers, and builds the section 4 output. It never calls a language model. |
| Engine | `engine/` | Pure Python with no dependencies: clean inputs, derive numbers, find conflicts, weight, filter, score, search stacks, explain, estimate cost. |
| Command line | `cli.py` | Runs scenario files and writes their output JSON; also prints recommendations for the built-in presets. |
| Language-model layer | `engine/llm.py`, `brief.py`, `summary.py` | Optional. Turns a free-text description into suggested answers the user confirms, and rewords explanations. Every output is checked, and every feature has a rule-based fallback. |
| Data | `data/` | Knowledge base (`data/kb/`), compatibility rules, questionnaire, glossary, presets, score rubric, explanation templates. |

## Technology used, with versions

| Part | Technology and version |
|---|---|
| Language | Python 3.12.10 (the code runs on Python 3.9 to 3.14) |
| Web framework | FastAPI 0.142.2 on Starlette 1.7.0, Pydantic 2.13.5, served by Uvicorn 0.54.0 |
| Tests | pytest 9.1.1, HTTPX 0.28.1 (the API test client) |
| Frontend | HTML, CSS and JavaScript in the browser, no framework, no third-party script |
| Optional language model | Google Gemini API through its OpenAI-compatible endpoint (free tier), called only when an API key is set |

`requirements.txt` gives the version ranges and `requirements.lock.txt` the exact versions the tests ran with.

## Prerequisites

- Python 3.9 or newer (3.12 recommended) from <https://www.python.org/downloads/>. On Windows, the installer's `py` launcher is enough.
- Windows 10/11, macOS or Linux. Nothing else to install: no database and no Node.js. Docker is optional (see Docker Compose below).
- Internet on the first run only, to install the Python packages. After that the app runs offline.
- No API key is needed. Every feature works without one.

## Quick start: setup and run

1. Get the code: `git clone https://github.com/Paradox-73/StackSense26.git` and `cd StackSense26` (or download the `source/` folder of the submission and open it).
2. Start the app with one command. The first run creates `.venv/`, installs `requirements.txt`, starts <http://127.0.0.1:8000> and opens the browser. Ctrl+C stops it.
   - Windows (PowerShell or Command Prompt): `py run.py`
   - macOS / Linux: `python3 run.py`
   - Other port, no browser: `python run.py --port 8080 --no-browser`
3. In the browser, open **Scenario file** (<http://127.0.0.1:8000/scenario>) to load a scenario JSON, or use the questionnaire on the home page.

Manual setup, if you prefer to run each step:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt      # Windows: .venv\Scripts\python -m pip install -r requirements.txt
.venv/bin/python run.py                                  # Windows: .venv\Scripts\python run.py
```

Docker Compose, instead of Python (Docker Desktop on Windows or macOS, Docker Engine with the Compose plugin on Linux):

```bash
docker compose up --build      # builds the image, then serves http://localhost:8000; Ctrl+C stops it
docker compose run --rm stacksense python cli.py --scenario scenarios/public/P2.json   # a scenario file, in the container
```

- Another host port: `STACKSENSE_PORT=8080 docker compose up --build` (PowerShell: `$env:STACKSENSE_PORT="8080"; docker compose up --build`).
- A `.env` file next to `compose.yaml` is passed into the container, so `STACKSENSE_LLM=off` and the optional key work the same way.

Setup problems: see Troubleshooting in [`docs/REFERENCE.md`](docs/REFERENCE.md#troubleshooting).

## Run a scenario file

A scenario file follows the standard input schema (problem statement section 3.2). The six public scenarios are in `scenarios/public/` and nine edge cases (missing fields, invalid values, contradictions, air-gapped and others) in `scenarios/edge/`.

```bash
python cli.py --scenario scenarios/public/P2.json                       # print the output JSON
python cli.py --scenario scenarios/public/P2.json --out my_output.json   # write it to a file
python cli.py --scenario scenarios/public --out outputs                 # every file in a folder
```

- With a folder, or an `--out` that is not a `.json` file name, each output is written to `<out>/<scenario_id>_output.json`, for example `outputs/P2_output.json`. The command prints one line per scenario: its status, the four choices and the file written.
- A file may hold a JSON array of scenarios, as the organisers' `stacksense_public_scenarios.json` does: each element is run on its own and gets its own `<scenario_id>_output.json` (printed, or written to an `--out` `.json` file, the outputs are one JSON array), and `POST /api/scenario` with an array returns an array of outputs.
- Use the same Python as the app: `.venv/bin/python cli.py ...` (Windows: `.venv\Scripts\python cli.py ...`) after the first `run.py`, or any Python 3.9+ (the command line needs no packages).
- In the browser: **Scenario file** (`/scenario`) loads a JSON file or a public example, shows the result and downloads it with **Download output JSON**.
- Over HTTP: `POST /api/scenario` with the scenario as the body returns the output JSON.
- A file with invalid fields gives `"status": "invalid_input"`, every problem in `validation_errors` and `"stack": null`. A file that is not JSON at all gives the same status with the parse error.
- `outputs/P1_output.json` ... `P6_output.json` in this repository are the engine's output for the public scenarios; `tests/test_llm_off.py` fails if they differ from what the engine returns now.

## Switch off the language model

The language model is optional and never chooses a component. To switch off every language-model call (no request is sent and no saved answer is served):

- Environment variable: `STACKSENSE_LLM=off` (PowerShell: `$env:STACKSENSE_LLM="off"`; macOS / Linux: `export STACKSENSE_LLM=off`), or the same line in a `.env` file (see `.env.example`).
- Flag: `python run.py --no-llm` for the app, `python cli.py --no-llm ...` for the command line.
- Without an API key no call is made either. `GET /api/health` shows `llm_enabled` and `llm_switched_off`.

The stack does not change when the switch is off: `tests/test_llm_off.py` runs the public scenarios and every preset with a fake model switched on and then off and compares the stacks. Scenario files never use the model at all.

## Project structure

```
app/            web app: main.py (FastAPI routes), static/ (questionnaire, scenario page, styles, fonts)
engine/         the engine: standard.py (scenario format), profile.py, conflicts.py, scoring.py, recommender.py,
                advice.py, explain.py, stack.py, whatif.py, and the optional language-model layer (llm.py, brief.py, summary.py)
data/           kb/ (frontend, backend, database, hosting, compatibility rules), questions.json, presets.json,
                glossary.json, rubric.json, explain_templates.json, llm_cache/ (saved model answers)
scenarios/      public/ (P1-P6 from the problem statement), edge/ (E1-E9 edge cases)
outputs/        the engine's output JSON for P1-P6
tests/          pytest suite (python -m pytest); benchmark/ holds the answer key for tools/bench.py
tools/          benchmark, fuzz test, question-influence study, screenshots, report and package builders
report/         report.md (source of the PDF), screenshots/, generated tables (sources.md, validation.md ...)
docs/           architecture figures and REFERENCE.md (API, configuration, scoring detail, troubleshooting)
cli.py, run.py  command line and one-command launcher
```

## Credits

Libraries (open source):

- [FastAPI](https://fastapi.tiangolo.com/) (MIT), [Starlette](https://starlette.dev/) (BSD-3), [Pydantic](https://docs.pydantic.dev/) (MIT), [Uvicorn](https://uvicorn.dev/) (BSD-3): the web app
- [pytest](https://docs.pytest.org/) (MIT) and [HTTPX](https://www.python-httpx.org/) (BSD-3): the tests
- Build tools only, not needed to run the app: [markdown-it-py](https://github.com/executablebooks/markdown-it-py) (MIT), [pypdf](https://github.com/py-pdf/pypdf) (BSD-3), [Playwright for Python](https://playwright.dev/python/) (Apache-2.0) and Google Chrome, for the report PDF and the screenshots
- Fonts bundled in `app/static/fonts/`: [Fraunces](https://github.com/undercasetype/Fraunces) and [Geist and Geist Mono](https://github.com/vercel/geist-font), SIL Open Font License 1.1 ([`OFL.txt`](app/static/fonts/OFL.txt))

APIs:

- [Google Gemini API](https://ai.google.dev/gemini-api/docs/openai) (hosted, optional, free tier): the default OpenAI-compatible chat API for the language-model features; [OpenRouter](https://openrouter.ai/) or another compatible API can be configured instead.

Datasets:

- None is shipped. The [Stack Overflow Developer Survey 2025](https://survey.stackoverflow.co/2025/technology) is cited as a proxy for hiring pools, and the INR exchange rate is the FBIL reference rate.

Sources:

- Every technology, rule and question cites official documentation, pricing pages or vendor compliance pages. The register of 344 URLs is in [`report/sources.md`](report/sources.md).
- Methods the design follows: [expert systems](https://en.wikipedia.org/wiki/Expert_system), the [weighted sum model](https://en.wikipedia.org/wiki/Weighted_sum_model), counterfactual explanations (Wachter, Mittelstadt and Russell, [2017](https://arxiv.org/abs/1711.00399)), and the quality attributes of [ISO/IEC 25010](https://www.iso.org/standard/78176.html) and the [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/).
- Key references: Google SRE book ([availability table](https://sre.google/sre-book/availability-table/)), Martin Fowler ([MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html)), [Team Topologies](https://teamtopologies.com/key-concepts), [HHS HIPAA cloud guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/health-information-technology/cloud-computing/index.html), [PCI SSC document library](https://www.pcisecuritystandards.org/document_library/), [MeitY DPDP framework](https://www.meity.gov.in/data-protection-framework), [RBI storage of payment system data (2018)](https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=11244), [endoflife.date](https://endoflife.date/) and the [Microsoft lifecycle pages](https://learn.microsoft.com/lifecycle/) for end-of-life checks.

## Run the checks

- Tests (a few minutes): `.venv/bin/python -m pytest` (Windows: `.venv\Scripts\python -m pytest`)
- Benchmark against the answer key: `python tools/bench.py`; random-input fuzz test: `python tools/fuzz.py`
- Report PDF and screenshots (needs Google Chrome and `requirements-dev.txt`): `python tools/capture_screenshots.py`, then `python tools/build_report.py`
- Submission folder: `python tools/package_submission.py`

## Key results

- **Tests:** 975 tests, including checks that every warning code is tested, that `outputs/` matches the engine and that the numbers in this file match the code (`tests/test_docs.py`).
- **Benchmark** (`python tools/bench.py`): 40 project briefs scored against an answer key written before measurement. Result: 81% top-1 (128 of the 158 layer picks that have a best pick) and 96% acceptable (154 of all 160 layer picks); held-out 72% and 95%. Ten briefs were held out and not used for tuning. The key was written by a language model playing three architect personas, blind to the engine, not by human architects.
- **LLM-only comparison** (`python tools/llm_baseline.py --show`, an offline experiment, not part of the engine): the same 40 briefs answered by a language model alone, then graded by the rules. LLM 84% top-1 on 158 picks, 94% acceptable on 160, against the engine's 81% and 96%, but the model breaks a hard requirement in 7 of the 40 briefs; the engine's own picks break none.
- **Random projects** (`python tools/fuzz.py --n 1000 --growth-n 100`): 1,000 seeded random projects against 15 properties (hard constraints, the same output on a repeat, renaming and reordering changing nothing, no return to an earlier pick as users grow): 0 violations.
- **Questions:** the questionnaire has 14 ready-made scenarios (presets), and every one of its 42 questions changed a pick at least once in the question-influence study (`python tools/question_influence.py`, 8,159 re-runs).

More detail: [`docs/REFERENCE.md`](docs/REFERENCE.md) and the report (`report/report.md`, built as the PDF in the submission folder).
