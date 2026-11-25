# RPA: Routine Discovery to Robot

A mined routine becomes a robot that actually clicks. This is Ishtiaq's slice of the three-person RPA thesis project (Mondira's course), built October to November 2026.

## Why

Routine-discovery papers stop at a discovered process model. This repo closes the loop: export the routine to JSON, then replay it against real apps so an audience can watch the work happen.

## Pipeline

A replicated de Leoni routine-discovery pipeline produces `routine.json` (14 actions). `export_routine.py` connects the routine to a label map. `run_bot.py` replays the routine in a browser against `mock_env.html`. `run_bot_desktop.py` deploys the same extracted program to real Microsoft Excel (win32com), the live form (Playwright), and a real Gmail send through SMTP.

The authors' `functions.py` was never edited. Our runner replays their notebook flow and adapters work around defects in their shipped glue, so the deviation is diffable.

## Receipts

- 9 public process logs from figshare dataset 12543587.
- Full noise grid: 9 logs x 4 levels x 10 runs = 360 rows.
- Clean-log Jaccard score 1.000 on log 1.
- Browser replay: 14 of 14 actions in 30.9 seconds.
- Desktop robot: real Excel edits, an audit column appended and SAVED into the workbook, and a real email sent over SMTP.
- The map is keyed by `routine.json` sequence because labels repeat: `copy_B_Excel` occurs at seq 10 AND 12. Label-keyed lookups silently drop the second.

## Screenshots

`shots/final.png`, `shots/real_excel_final.png`, `shots/desktop_*.png` are real captures, not mockups.

## Run the mock replay (Linux or Windows)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-demo.txt
python3 -m playwright install chromium
python3 run_bot.py
```

## Run the desktop demo (Windows, real Excel)

1. Open a CMD window inside this folder (address bar, type `cmd`, Enter).
2. `python -m venv .venv-win` then `.venv-win\Scripts\activate`
3. `pip install -r requirements-demo.txt`
4. Fill `desktop_map.json` mail settings with a **demo-only** Gmail account and its 16-character App Password (2FA required). Leave the placeholder values to keep the human-click fallback.
5. `python run_bot_desktop.py`

`LAUNCH.sh` and `WINDOWS_OPENCODE_PROMPT.md` are the original runbook material.

## Safety and ethics

- The live form's Submit button is never clicked. It is hovered with a halo only.
- The Gmail compose path leaves the human in control unless a demo-only SMTP account is explicitly configured.
- No real credentials, student records, or identifiers are in this repo. The desktop map ships with placeholder mail settings. If a password was ever used in a live demo, rotate it.
- The base paper is de Leoni et al., COOPIS 2025, DOI 10.1007/978-3-032-15538-2_26. This repo is a replication and extension, not a copy of their system.

## Teammate attribution

The thesis is a three-person project: Koushiq Chowdhury did data collection and preprocessing; Sharin Akter Shashi did sessionization, encoding, clustering and the U2/U3 automation; Ishtiaq Ahmed did post-cluster evaluation, the 360-row noise grid, and this routine-to-robot executor. Ask teammates before publishing their code.

## Author of this repo slice

Ishtiaq Ahmed, Department of CSE, Notre Dame University Bangladesh.
