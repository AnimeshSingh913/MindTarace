# MindTrace

**Explains where reasoning went wrong, without ever giving the answer.**

You paste a problem and the reasoning behind a wrong answer. MindTrace names the mistake,
explains why it happens and how to rethink it, and leaves the solving to you.

It can run fully locally on a small model through [Ollama](https://ollama.com), or online
against any OpenAI-compatible API (Groq, OpenRouter, Together, OpenAI and others). See
[Deploying online](#deploying-online).

MindTrace is a ground-up rebuild of an earlier "Reasoning Mistake Analyzer" prototype. The
[Changes from the prototype](#changes-from-the-prototype) section lists what was fixed.

---

## Modes

| Mode | Persona | Output |
|---|---|---|
| **Education** | Patient tutor | Mistake type, pattern, confidence, consistency check, what went wrong, why it happens, how to rethink, what would have prevented it, a reflection question |
| **Interview** | Neutral evaluator (no coaching) | Mistake type, pattern, confidence, consistency check, interviewer assessment, risk signals |
| **Research** | Cognitive scientist | Error category, cognitive pattern, confidence, agreement with your analysis, interpretation, why it occurs, broader implications, related biases |

Each mode is one declarative spec in [`backend/mindtrace/modes.py`](backend/mindtrace/modes.py).
That spec generates the prompt's output section, the JSON schema the model must follow, and
the mapping onto the API response, so adding a field means changing one line.

## How it works

```
request ─▶ rate limit ─▶ clean input ─▶ fenced prompt ─▶ LLM (JSON) ─▶ parse ─▶ guardrail ─▶ response
                                                            │                 │ retry once at T=0
                                                            └─ judge model ◀──┘ (only when needed)
```

1. **Clean.** Control characters are stripped and user text is fenced in `<problem>` and
   `<reasoning>` tags that it cannot close. The text is **not** rewritten: `km/h` stays `km/h`.
2. **Generate.** A separate system prompt, a token limit and an optional seed are sent to one of:
   - **Ollama:** `POST /api/chat` with structured output (`format` = the mode's JSON schema).
   - **OpenAI-compatible:** `POST /chat/completions` with `response_format` (`json_object`
     by default, or `json_schema` where the model supports it).
3. **Parse.** The JSON is validated against the mode's fields (enums normalised, lists split).
   A lenient text parser handles models that ignore the schema (`**Header:**`, `## Header`).
   One retry at temperature 0 runs if the main explanation is missing.
4. **Guard.** See below. A blocked response carries **no** model text.
5. **Respond.** Summary fields plus ordered `sections` for display.

### Guardrail: how it stays answer-free

| Tier | Catches | Action |
|---|---|---|
| Answer statements | "the correct answer is…", "answer: 26", "it should have been 26" (but not "the student's final answer is 40") | Block |
| Equality with a new number | "= 26", "equals twenty-six", "is equal to 26", where the number is not in the input | Block |
| New numbers | Any number, in digits or words ("comes out to forty-eight"), that is not in the problem or reasoning | Ask the judge model (configurable: `judge`, `block`, `allow`) |
| Always-judge (opt-in) | Conceptual leaks on non-numeric problems | Ask the judge model |
| Fail-closed | Judge timeout or error, missing judge, ambiguous verdict, guard crash | Block |

The judge (`qwen2.5:0.5b` by default) sees the problem, the reasoning and the analysis, and
returns structured JSON `{"reveals_answer": bool}`.

The "new number" check replaces the old verb keyword list. That list was bypassed by 12 of 14
held-out phrasings ("lands on", "totals", "resolves to"), because a leaked numeric answer
almost always has to *mention a new number*, whatever verb surrounds it. This is still not
perfect. A leak that only *confirms* one of the person's own numbers without an answer phrase,
or a conceptual leak on a non-numeric problem, relies on the prompt and (optionally)
`MINDTRACE_JUDGE_ALWAYS=true`.

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/analyze` | Analyse reasoning |
| `GET` | `/api/health` | Provider reachability, whether the model and judge are available (cached 60s for hosted providers) |
| `GET` | `/api/live` | Liveness probe for the host; never calls the model |
| `GET` | `/api/modes` | Modes and their fields |
| `GET` | `/docs` | Interactive OpenAPI docs |

```jsonc
// POST /api/analyze
{ "problem": "A rectangle is 8 cm by 5 cm. Find its perimeter.",
  "reasoning": "I multiplied 8 by 5 and got 40 cm.",
  "mode": "education" }                    // education | interview | research

// 200, ok
{ "mode": "education", "status": "ok",
  "mistake_type": "Conceptual", "reasoning_pattern": "Formula Confusion",
  "confidence": "High", "agreement": "Yes",
  "explanation": "The reasoning used the formula for area…",
  "sections": [{ "key": "what_went_wrong", "title": "What Went Wrong", "content": "…" }, …],
  "meta": { "model": "qwen2.5:3b", "latency_ms": 7420, "judge_called": false, "missing_fields": [] } }

// 200, blocked (no model text is ever included)
{ "mode": "education", "status": "blocked",
  "block": { "reason": "explicit_answer", "message": "The analysis started to state the answer…" },
  "meta": { … } }
```

Errors:

| Status | Meaning |
|---|---|
| `422` | Invalid input: blank, over 4,000 characters, or unknown mode |
| `429` | Rate limited, by MindTrace or by the provider. Includes `Retry-After` |
| `502` | Model failure or unparseable output |
| `503` | Provider unreachable, model missing, or API key rejected |
| `500` | Unexpected error. Details stay in the server log |

## Getting started

**Prerequisites:** Python 3.10+, Node 18+, and [Ollama](https://ollama.com/download) (not needed for mock mode).

```bash
ollama pull qwen2.5:3b
ollama pull qwen2.5:0.5b
pip install -r backend/requirements.txt
npm --prefix frontend install
```

**Windows:** `start.bat` opens the API and the web app in two windows. `start.bat mock`
runs without Ollama, using canned answers.

**Manual:**

```bash
# Terminal 1: API (http://127.0.0.1:8000/docs)
cd backend
python -m uvicorn mindtrace.main:app --reload --port 8000

# Terminal 2: web app (http://localhost:5173), which proxies /api to :8000
cd frontend
npm run dev
```

Configuration is through `MINDTRACE_*` environment variables. See [`.env.example`](.env.example).

To use a hosted model locally instead of Ollama, set these before starting the API:

```bash
export MINDTRACE_PROVIDER=openai
export MINDTRACE_OPENAI_BASE_URL=https://api.groq.com/openai/v1
export MINDTRACE_OPENAI_API_KEY=<your key>
export MINDTRACE_MODEL=<a model ID from your provider's list>
```

(In PowerShell, use `$env:MINDTRACE_PROVIDER = "openai"` and so on.)

## Deploying online

The frontend goes on **Vercel**, the API on **Render**, and the model is a hosted
**OpenAI-compatible API**. Ollama is not used in production: typical web hosts can't run a
model on their free or small plans.

```
Browser ──▶ Vercel (static React app) ──▶ Render (FastAPI) ──▶ OpenAI-compatible LLM API
```

### 1. Get an API key and pick a model

Any provider with an OpenAI-compatible endpoint works:

| Provider | `MINDTRACE_OPENAI_BASE_URL` |
|---|---|
| Groq | `https://api.groq.com/openai/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| Together | `https://api.together.xyz/v1` |
| OpenAI | `https://api.openai.com/v1` |

Pick a model ID from the provider's current model list (an instruction-tuned model of about
8B parameters or larger works well) and set it as `MINDTRACE_MODEL`. The judge uses the same
model unless you set `MINDTRACE_JUDGE_MODEL`.

If the provider rejects `response_format`, set `MINDTRACE_OPENAI_JSON_MODE=none`; the
lenient parser still handles the output. Some reasoning-style models also reject the
`temperature` and `max_tokens` parameters, so prefer a standard chat model.

### 2. Deploy the API on Render

1. Push this repo to GitHub.
2. In Render, choose **New → Blueprint** and pick the repo. Render reads
   [`render.yaml`](render.yaml).
3. When prompted, fill in:
   - `MINDTRACE_OPENAI_API_KEY`: your provider key
   - `MINDTRACE_MODEL`: the model ID
   - `MINDTRACE_CORS_ORIGINS`: leave as `https://placeholder` for now; you'll set it in step 4
4. Deploy, then copy the service URL (e.g. `https://mindtrace-api.onrender.com`) and open
   `/api/health` on it. You should see `"reachable": true`.

The blueprint already turns on rate limits (5 per minute and 40 per hour per IP, 500 per day
in total) and runs Uvicorn with `--proxy-headers`, so the limits see real visitor IPs. If you
change provider, edit `MINDTRACE_OPENAI_BASE_URL` in the dashboard.

> Render's free plan sleeps after a period of inactivity. The first request after that takes
> about 30–60 seconds while it wakes up. The frontend waits up to 150 seconds and then shows a
> "try again" message.

### 3. Deploy the frontend on Vercel

1. In Vercel, choose **Add New → Project** and pick the same repo.
2. Set **Root Directory** to `frontend`. The framework preset (Vite), build command and
   output directory (`dist`) are detected automatically.
3. Add the environment variable `VITE_API_URL` = your Render URL, with no trailing slash.
4. Deploy and copy the Vercel URL.

`VITE_API_URL` is baked in at build time, so redeploy the frontend after changing it.

### 4. Connect them

Back in Render, set `MINDTRACE_CORS_ORIGINS` to your Vercel URL (comma-separate several, e.g.
a custom domain). The service restarts. Open the Vercel URL: the status pill should show
**Ready**.

### Keeping costs safe

- Each analysis is one model call, plus a judge call when a new number appears.
- `MINDTRACE_DAILY_REQUEST_CAP` is a hard stop across all visitors. Set it to what you're
  willing to pay for in a day.
- Set a spending limit in your provider's dashboard as well.
- Rate-limit state is in memory and per instance. That's right for a single Render instance,
  but use a shared store such as Redis if you scale out.

## Tests

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest   # 102 tests, no model or key needed
cd frontend && npm test && npm run build                                 # API client + result panel, typecheck, build
```

The backend suite uses a scriptable fake LLM and an `httpx.MockTransport`. It covers:
- the guardrail tiers, including regression cases for every prototype bug
- the parser: JSON, markdown headers, malformed output
- the API contract: blocked responses contain no model text, fail-closed at the API level, error mapping, validation, CORS
- both LLM clients, rate limiting and config validation

## Project structure

```
MindTrace/
├── backend/
│   ├── mindtrace/
│   │   ├── main.py          FastAPI app factory, routes, error mapping
│   │   ├── pipeline.py      clean → generate → parse → guard → respond
│   │   ├── modes.py         mode specs → prompt, JSON schema, field roles
│   │   ├── guardrails.py    answer statements, novel numbers, judge, fail-closed
│   │   ├── numerics.py      numbers in digits / fractions / words
│   │   ├── parser.py        JSON + lenient text fallback
│   │   ├── sanitize.py      input cleaning, prompt fencing
│   │   ├── llm.py           Ollama, OpenAI-compatible and mock clients
│   │   ├── ratelimit.py     per-IP windows + daily cap
│   │   ├── schemas.py       request / response models
│   │   ├── config.py        MINDTRACE_* settings
│   │   └── prompts/         shared rules + one persona file per mode
│   └── tests/
├── frontend/                React 18 + Vite + Tailwind (3 runtime dependencies)
│   └── src/{components,lib,test}
├── render.yaml              Render blueprint for the API
├── start.bat
└── .env.example
```

## Changes from the prototype

| Prototype issue | MindTrace |
|---|---|
| "Fail-closed" judge failure still returned the analysis (API only checked one message string) | The guard verdict is a value; anything but `safe` returns a blocked response |
| Blocked responses included `raw_response` with the leaked answer | Blocked responses contain no model text |
| Judge read "YES… NOT" as safe (`"NO" in "NOT"`) and never saw the problem | Judge returns schema-constrained JSON, sees the problem; ambiguous means blocked |
| Bare phrases "solution is" / "final answer" blocked safe text | Context-aware answer patterns that ignore descriptions of the person's own answer |
| Sanitizer rewrote `=` → "equals", then its own regex fired when the model quoted the student; also mangled `km/h`, `well-known` | Text preserved and fenced instead |
| Keyword-triggered judge missed 12/14 held-out leaks | Novel-number detection (digits and words) decides when to judge |
| Header scraping: bold headers → "Unknown", any line ending in ":" became a section, interview output duplicated | JSON schema output + mode-aware parser; one explanation field per mode |
| ANSI cleaner deleted real text (`[2D view]`); `ollama run` fallback pointless | HTTP API only; no ANSI handling needed |
| `MAX_TOKENS` never sent; blocking calls in `async` endpoint; global failure state; no subprocess timeout | `num_predict` sent; async `httpx`; per-request verdicts; timeouts everywhere |
| Prompts loaded relative to the working directory | Loaded relative to the package |
| CORS `*` with credentials; `str(e)` returned to clients; no input limits; free-form `mode` | Configured origins, no credentials; generic 500s; length limits; `Literal` modes |
| Hard-coded `localhost:8000`; newlines collapsed; unused preset data; ~45 unused UI components and ~50 dependencies | Dev proxy / `VITE_API_URL`; `whitespace-pre-line`; 3 runtime dependencies |
| Three different product names, committed `__pycache__`, push scripts aimed at another person's repo | One brand, proper `.gitignore`, no push scripts |
| Eval scripts only, run on hand-written outputs | 102 pytest unit/API tests + frontend tests |

## Known limitations

- Small local models on CPU take roughly 5 to 30 seconds per analysis. Hosted APIs are usually much faster.
- The hosted client has only been tested against mocked HTTP responses. Provider quirks with
  `response_format`, `seed` or `max_tokens` may require `MINDTRACE_OPENAI_JSON_MODE=none` or a
  different model.
- The guardrail is layered, not perfect. See the guardrail section for what it does and does not catch.
- Mock mode returns the same generic analysis for every input. It exists to exercise the UI and API.
