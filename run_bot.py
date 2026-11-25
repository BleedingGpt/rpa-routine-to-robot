#!/usr/bin/env python3
"""
run_bot.py — Component 4 of the closing-the-loop demo.

THE EXECUTOR. Reads demo_bot/routine.json (the program — auto-extracted
from OUR replicated de-Leoni pipeline) + label_map.json (the translation
table). Drives the mock environment page in a REAL browser window:
gliding ghost cursor, typing, clicks, Excel handoffs, attended pauses.

This is the smartRPA pattern (routine -> executable robot), miniaturized:
  smartRPA : abstracted log  -> script generator -> Automagica engine
  OURS     : routine.json    -> run_bot.py      -> Playwright engine

Usage:
  python run_bot.py                     # attended: pauses at credentials
  python run_bot.py --auto              # fully automatic typing
  python run_bot.py --beats 0.65        # pacing between actions (s)
  python run_bot.py --fast              # quick rehearsal (--beats 0.18)
  python run_bot.py --headless --fast --shot shots   # no-window test
"""
import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent


def play(page, JS):
    """Run a JS snippet that returns a Promise and await its value."""
    return page.evaluate("expr => expr", JS)


def wait_user_input(page, selector, expected, poll=0.15, timeout=180):
    """Attended pause: wait until the human typed something."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        v = page.eval_on_selector(selector, "el => el.value")
        if v and v.strip():
            return v
        time.sleep(poll)
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true",
                    help="type the credential values automatically (no pause)")
    ap.add_argument("--beats", type=float, default=0.65)
    ap.add_argument("--fast", action="store_true", help="--beats 0.18")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--shot", default="", help="dir for checkpoint screenshots")
    args = ap.parse_args()
    if args.fast:
        args.beats = 0.18

    routine = json.loads((HERE / "routine.json").read_text())
    labelmap = json.loads((HERE / "label_map.json").read_text())["map"]
    actions = routine["actions"]
    prov = routine.get("provenance", {}).get("pipeline_result") or {}

    session_kind = "ATTENDED" if not args.auto else "AUTOMATIC"
    print(f"== RUN-BOT :: log{routine['log']} session{routine['session']} :: "
          f"{len(actions)} actions :: mode {session_kind} ==")
    if prov:
        r1 = prov.get("routine_1", {})
        print(f"   provenance: routine_1 traces={r1.get('Traces')} "
              f"JC={r1.get('JC')} fitness={r1.get('Fitness')} "
              f"(vs GT {r1.get('best_gt')})")

    with sync_playwright() as pw:
        # engine: system Google Chrome first (zero download, this machine
        # already has /usr/bin/google-chrome-stable thanks to the mermaid
        # pipeline); bundled Chromium as fallback.
        try:
            browser = pw.chromium.launch(channel="chrome",
                                         headless=args.headless)
            engine = "system-chrome"
        except Exception:
            browser = pw.chromium.launch(headless=args.headless)
            engine = "bundled-chromium"
        if not args.headless:
            page = browser.new_page(no_viewport=True)
        else:
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
        print(f"   engine: {engine}")
        page.goto("file://" + str(HERE / "mock_env.html"))
        page.wait_for_function("window.DemoReadyVal === true", timeout=5000)
        page.evaluate(f"window.DEMO.start({len(actions)})")

        clipboard = None
        n = len(actions)
        t0 = time.time()
        for i, act in enumerate(actions, 1):
            label = act["label"]
            spec = labelmap.get(label)
            if spec is None:
                raise RuntimeError(f"label_map.json has no rule for {label}")
            src = ("Excel" if act.get("source") == "Excel" else "Web")

            page.evaluate(
                "([c, l, s]) => window.DEMO.progress(c, l, s)",
                [i - 1 + 0.0, # progress shows current being executed
                 label, src],
            )
            page.evaluate("([t, k]) => window.DEMO.tick('▶ ' + t, k)",
                          [label, "do"])
            time.sleep(args.beats * 0.5)

            g = spec["gesture"]

            if g == "excel_open":
                page.evaluate("() => window.DEMO.excelShow()")
                time.sleep(args.beats)

            elif g == "navigate":
                page.evaluate("() => window.DEMO.screen('login')")
                time.sleep(args.beats)

            elif g == "type":
                sel = spec["target"]
                if spec.get("attend") and not args.auto:
                    page.evaluate("s => window.DEMO.attend(s)", sel)
                    page.evaluate("t => window.DEMO.tick('⏸ human input required (attended robot — smartRPA-style requirement point)', 'human')",
                                  [label])
                    got = wait_user_input(page, sel,
                                          act.get("Value") or "")
                    page.evaluate("s => window.DEMO.attendDone(s)", sel)
                    page.evaluate("t => window.DEMO.tick('✓ human input accepted → robot continues', 'human')")
                else:
                    # ghost cursor + caret-accurate typing from the log value
                    page.evaluate("s => window.DEMO.glide(s)", sel)
                    time.sleep(args.beats * 0.6)
                    val = act.get("Value") or ""
                    if spec.get("value_from") == "Value" and val:
                        page.evaluate(
                            "([s, t]) => window.DEMO.typeInto(s, t, 55)",
                            [sel, val],
                        )
                time.sleep(args.beats)

            elif g == "click":
                page.evaluate("s => window.DEMO.glide(s)", spec["target"])
                time.sleep(args.beats * 0.5)
                page.click(spec["target"])
                page.evaluate("s => window.DEMO.ripple(s)", spec["target"])
                # screen transitions implied by the routine
                if spec["target"] == "#btn-confirm":
                    page.evaluate("() => window.DEMO.spinner(true)")
                time.sleep(args.beats)
                if spec["target"] == "#btn-button1":
                    page.evaluate("() => window.DEMO.screen('records')")
                if spec.get("finish"):
                    page.evaluate("() => window.DEMO.screen('done')")
                    time.sleep(0.6)
                    page.evaluate("() => window.DEMO.finish()")

            elif g == "wait":
                page.evaluate(
                    "t => window.DEMO.tick('⏳ ' + t, 'wait')", spec["msg"])
                page.evaluate("() => window.DEMO.spinner(true)")
                time.sleep(args.beats * 2.2)
                page.evaluate("() => window.DEMO.spinner(false)")
                page.evaluate("() => window.DEMO.banner(true)")
                page.evaluate("() => window.DEMO.screen('menu')")
                time.sleep(args.beats)

            elif g == "excel_copy":
                cell = "B" + str(act.get("Row") or "?")
                page.evaluate("c => window.DEMO.excelSelect(c)", cell)
                val = act.get("Value") or ""
                page.evaluate("t => window.DEMO.copyChip(t)", val)
                clipboard = val
                page.evaluate("t => window.DEMO.tick('⧉ clipboard ← ' + t, 'copy')",
                              [val])
                time.sleep(args.beats * 0.8)

            elif g == "paste":
                sel = spec["target"]
                page.evaluate("s => window.DEMO.glide(s)", sel)
                time.sleep(args.beats * 0.5)
                v = clipboard if spec.get("value_from") == "clipboard" \
                    else (act.get("Value") or "")
                page.evaluate("([s, t]) => window.DEMO.fillInstant(s, t)",
                              [sel, v])
                page.evaluate("t => window.DEMO.tick('⇩ pasted → ' + t, 'paste')",
                              [v])
                time.sleep(args.beats * 0.8)
            else:
                raise RuntimeError(f"unknown gesture {g}")

        dt = time.time() - t0
        if args.shot:
            sdir = HERE / args.shot
            sdir.mkdir(exist_ok=True)
            page.screenshot(path=str(sdir / "final.png"))
        page.evaluate("t => window.DEMO.tick('⏱ completed in '+" +
                      json.dumps(f"{dt:.1f}s")+", 'done')")
        print(f"== DONE :: {n}/{n} actions in {dt:.1f}s :: exit ok ==")
        # keep the final screen briefly for applause / photos
        try:
            page.wait_for_timeout(4000)
        except Exception:
            pass
        browser.close()


if __name__ == "__main__":
    main()
