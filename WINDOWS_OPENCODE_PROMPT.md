# PROMPT for Windows OpenCode — Stand Up the RPA Demo Bot

> Copy-paste this whole file into your OpenCode session on the Windows PC.
> PRECONDITION: the `demo_bot/` folder from the Linux machine is already placed
> somewhere (e.g. `C:\projects\RPA_Thesis\03_Our_Work\demo_bot\`) with the
> files listed in Step 0. Transfer ONLY these 8 files (~44KB total):
>
>   run_bot.py  run_bot_real.py  export_routine.py  mock_env.html
>   label_map.json  real_map.json  routine.json  LAUNCH.sh
>
> DO NOT copy `.venv/` or `shots/` — they are rebuilt fresh.

---

## CONTEXT (read first — don't skip)

This is the **demo bot** from our RPA thesis (replication of de-Leoni et al.,
CoopIS'25 — "Routine Log extraction in RPA", arXiv 2510.08118). The pipeline
(sequence segmentation → count-vector encoding → K-Means/DBSCAN/HDBSCAN) was
replicated on the Linux machine; its winning cluster `routine_1` on log1
covered all 100 sessions (JC 1.000). `export_routine.py` converted that
cluster into **routine.json — a 14-action ordered program for log1/session1,
extracted from the log itself, ZERO hand-written steps**.

The bot is the smartRPA pattern miniaturized:

    smartRPA : abstracted log -> script generator -> Automagica engine
    OURS     : routine.json    -> run_bot.py      -> Playwright engine

Three components:
1. **export_routine.py** — routine extractor (pipeline artifacts in,
   routine.json out). OPTIONAL on this machine: it needs the replication
   folder (`../replication/Transformed_Logs_and_Results/...` + `../replication/results/clean_ours.jsonl`)
   which likely did NOT transfer. That's fine — routine.json is already
   generated and committed in the folder. Just verify export_routine.py
   syntax compiles; do NOT try to run it without the artifacts.
2. **run_bot.py** — MOCK executor: drives `mock_env.html` (self-contained
   fake ERP/Excel environment opened via `file://` protocol) with a gliding
   ghost cursor, caret-accurate typing, clicks, an Excel panel tab
   (simulated INSIDE the HTML — no real Excel dependency), attended pauses.
3. **run_bot_real.py** — REAL executor: same routine.json drives the live
   page `https://demoform.frontiertechy.com/form-a/` (WordPress/Fluent Forms)
   two-window style: Excel panel in one window, real form in another,
   keystroke-by-keystroke with ghost-mouse effects injected via JS.
   **SAFETY: it must NEVER click Submit. It hovers the submit button and
   prints the DOM state as hard proof instead. Keep that behavior intact.**

## YOUR JOB (do in order)

### Step 0 — Verify files
`demo_bot/` must contain exactly: run_bot.py, run_bot_real.py,
export_routine.py, mock_env.html, label_map.json, real_map.json,
routine.json (14 actions, log 1, session 1), LAUNCH.sh. If any missing → stop and ask.

### Step 1 — Python environment (Windows)
- Python 3.10+ required. Create venv in `demo_bot/.venv` (Windows layout:
  `Scripts\`, not `bin\`).
- `pip install playwright` — NOTHING else (no playwright extras).
- Engine note: run_bot.py and run_bot_real.py try `pw.chromium.launch(channel="chrome")`
  first (system Chrome, zero download), with bundled Chromium as fallback.
  If the PC has Chrome installed → it just works. If not → `playwright install chromium`.

### Step 2 — Windows launcher
LAUNCH.sh is bash and won't run on Windows. Build `LAUNCH.ps1` (same CLI
contract): `--real` routes to run_bot_real.py, everything else to run_bot.py;
override `--auto`, `--beats F`, `--fast`, `--headless`, `--shot DIR` passthrough.

### Step 3 — Fix a known cosmetic bug BEFORE anything else
Line 9 of run_bot_real.py (module docstring) contains a stray Russian word:
`живет through real_map.json`. Replace with `lives through real_map.json`.
Do not touch anything else in the file.

### Step 4 — Verify: mock target (headless CI-style test)
```
.venv\Scripts\python run_bot.py --headless --fast --shot shots
```
PASS = last line `== DONE :: 14/14 actions * :: exit ok` + `shots/final.png`
created. The mock page also self-checks: `window.DemoReadyVal === true` gate
must pass within 5s.

### Step 5 — Verify: real target (headless, safe — submit is never clicked)
```
.venv\Scripts\python run_bot_real.py --headless --fast --auto --shot shots
```
PASS = `== DOM STATE ON REAL PAGE ==` printout with First Name/Surname/
Job Group/Department/Personal Number/Designation/Duty Station populated +
`== DONE :: 14/14 actions * :: submit skipped ==` + `shots/real_final.png`
(full-page). Requires internet on this PC.

### Step 6 — Interactive demo check (visible window)
```
.venv\Scripts\python run_bot.py                 # attended: pauses at the 2 credential fields
.venv\Scripts\python run_bot_real.py --beats 0.7  # cinematic pacing
```
Attended contract: the robot stops at credential fields, waits up to 180s for
a human to type, then continues. `--auto` disables all pauses.

## RULES (non-negotiable)

1. `routine.json` is machine-generated provenance — NEVER hand-edit it. If it
   needs regeneration, that happens on the Linux machine via export_routine.py.
2. NEVER add a submit-click to run_bot_real.py. The safety veil is the demo's
   selling point ("closing the loop without pushing data to the live site").
3. mock_env.html and the label maps are demo artifacts from the thesis — fix
   path/OS issues if any, but don't redesign them.
4. All output paths are built with pathlib (cross-platform), so file:// URLs
   work on Windows as-is. Do NOT hardcode any `/home/...` or `C:\...` paths.
5. If Excel phase breaks on Windows: the Excel panel in BOTH executors is a
   `window.DEMO` simulation inside an HTML page, not a real Excel COM call.
   Nothing here should ever touch real Excel, COM objects, or sendkeys.

## DONE CRITERIA

- [ ] .venv builds, playwright installed, engine = system-chrome or chromium
- [ ] LAUNCH.ps1 exists, routes like LAUNCH.sh
- [ ] `живет` → `lives` fixed
- [ ] Mock headless run: 14/14 ok, final.png captured
- [ ] Real headless run: DOM state printed, submit skipped, real_final.png captured
- [ ] One attended visible-window run done with the human pausing/typing
- [ ] Report back: engine used, both DONE lines, screenshot paths
