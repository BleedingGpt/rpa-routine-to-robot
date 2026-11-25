#!/usr/bin/env python3
"""
export_routine.py — Component 1 of the closing-the-loop demo.

Pulls the winning routine's ordered action sequence from OUR
replicated de-Leoni pipeline artifacts (transformed log + clean
grid results) and writes demo_bot/routine.json, which the bot
executor (run_bot.py) consumes as its program.

NO hand-coding of actions: every action line below comes from
the log our pipeline processed. Provenance comes from
results/clean_ours.jsonl (run 27 Oct 2026, 16:01).

Usage:  python export_routine.py            (default log=1 session=1)
        python export_routine.py --log 2 --session 3
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REP = HERE.parent / "replication"
XES = (REP / "Transformed_Logs_and_Results" / "Our" /
       "Transformed_Log_Without_Noise" / "transform_log{n}.xes")
RESULTS = REP / "results" / "clean_ours.jsonl"

ATTR_KEYS = ("source", "Label", "Value", "Column", "Row", "Url",
             "Sheet", "FileName")


def parse_xes(path: Path):
    """Return list of event attribute-dicts from a single-trace XES."""
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"<event>(.*?)</event>", text, re.S)
    events = []
    for b in blocks:
        e = {}
        for m in re.finditer(r'key="([^"]+)"\s+value="([^"]*)"', b):
            k, v = m.group(1), m.group(2)
            e[k] = None if v in ("nan", "") else v
        events.append(e)
    return events


def split_sessions(events):
    """Sessions start at openFile_* (the log's demo session marker)."""
    starts = [i for i, e in enumerate(events)
              if (e.get("concept:name") or "").startswith("openFile")]
    bounds = starts + [len(events)]
    return [events[bounds[i]:bounds[i + 1]] for i in range(len(starts))]


def load_pipeline_result(log_n: int):
    """Find the log row in our clean-grid results (multiline JSON)."""
    if not RESULTS.exists():
        return None
    text = RESULTS.read_text()
    dec, rows, i = json.JSONDecoder(), [], 0
    while i < len(text):
        j = text.find("{", i)
        if j < 0:
            break
        obj, i = dec.raw_decode(text, j)
        if obj.get("log") == log_n:
            rows.append(obj)
    return rows[-1] if rows else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=int, default=1)
    ap.add_argument("--session", type=int, default=1)
    args = ap.parse_args()

    path = Path(str(XES).format(n=args.log))
    if not path.exists():
        sys.exit(f"transformed log missing: {path}")

    events = parse_xes(path)
    sessions = split_sessions(events)
    idx = args.session - 1
    if idx >= len(sessions):
        sys.exit(f"log{args.log} has {len(sessions)} sessions; "
                 f"requested #{args.session}")

    actions = []
    for n, e in enumerate(sessions[idx], start=1):
        actions.append({
            "seq": n,
            "label": e.get("concept:name"),
            "source": e.get("source"),
            **{k: e.get(k) for k in ATTR_KEYS},
        })

    result = load_pipeline_result(args.log)
    provenance = {
        "generator": "export_routine.py (demo_bot)",
        "extracted_from": str(path.relative_to(HERE.parent)),
        "pipeline": "de-Leoni et al. (CoopIS'25) technique - replicated "
                    "by our headless runner (src/run_ours.py), "
                    "authors' functions.py untouched",
        "clean_grid_run": "2026-10-27 16:01 (results/clean_ours.jsonl)",
        "notes": "routine_1 on log1 covered all 100 sessions; "
                 "this file = the exact action order the pipeline "
                 "clusters into routine_1 (no hand-written steps).",
    }
    if result:
        provenance["pipeline_result"] = {
            "log": result.get("log"), "k": result.get("k"),
            "routines": result.get("routines"),
            "empty_pct": result.get("empty_pct"),
            "routine_1": next((r for r in result.get("per_routine", [])
                               if r.get("Routine") == "routine_1"), None),
        }

    out = {
        "log": args.log,
        "session": args.session,
        "n_sessions_in_log": len(events) // max(1, len(sessions[idx])),
        "representative_session": (f"session {args.session} of "
                                   f"{len(sessions)} in log{args.log}"),
        "provenance": provenance,
        "actions": actions,
    }
    dest = HERE / "routine.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"wrote {dest} : {len(actions)} actions "
          f"(log{args.log}, session {args.session})")


if __name__ == "__main__":
    main()
