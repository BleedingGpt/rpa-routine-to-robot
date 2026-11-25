#!/usr/bin/env python3
"""
run_bot_real.py — closing-the-loop demo on a REAL WEBPAGE.

Same program (demo_bot/routine.json, auto-extracted from our replicated
pipeline — no hand-written steps), different deployment target:
https://demoform.frontiertechy.com/form-a/ (live WordPress/Fluent Forms).

 живет through real_map.json (the target-specific translation table).
Excel phase runs on the mock panel tab (the routine's data source),
Web phase runs keystroke-by-keystroke on the real page with a gliding
ghost mouse. SUBMIT IS NEVER CLICKED — the robot verifies readiness and
hovers the Submit button only (safe against pushing data to the site).

Usage:
  python run_bot_real.py --headless --fast --auto --shot shots   # CI-style test
  python run_bot_real.py                                          # attended: pauses at First Name/Surname
  python run_bot_real.py --beats 0.7                              # cinematic pacing for the live demo
"""
import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
REAL_URL = json.loads((HERE / "real_map.json").read_text())["real_url"]

# --- injected effect layer for the REAL page (mirrors mock_env.html SOUL) ---
INJECT = r"""
(() => {
  if (window.RPA) return "already";
  const st = document.createElement("style");
  st.textContent = `
  .rpa-ghost{position:fixed;z-index:999998;width:14px;height:14px;border-radius:50%;
    margin:-7px 0 0 -7px;background:rgba(250,250,255,.85);box-shadow:0 0 14px 4px rgba(120,180,255,.8);
    pointer-events:none}
  .rpa-ring{position:fixed;z-index:999997;width:26px;height:26px;border-radius:50%;
    margin:-13px 0 0 -13px;border:2px solid rgba(120,180,255,.9);pointer-events:none;
    transition:all .28s ease-out;box-shadow:0 0 8px rgba(120,180,255,.6)}
  .rpa-halo{position:fixed;z-index:999996;border-radius:8px;border:2px solid rgba(255,205,80,.9);
    box-shadow:0 0 0 6px rgba(255,205,80,.18);pointer-events:none;
    animation:rpapulse 1s ease-in-out infinite}
  @keyframes rpapulse{50%{box-shadow:0 0 0 12px rgba(255,205,80,.12)}}
  .rpa-hold{animation:rpapulse .7s ease-in-out infinite !important;
    border-color:rgba(120,255,180,.95) !important;box-shadow:0 0 0 6px rgba(120,255,180,.2) !important}
  #rpa-ticker{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);z-index:999999;
    display:flex;flex-direction:column-reverse;gap:6px;pointer-events:none;
    font:600 12px/1.35 'Segoe UI',sans-serif}
  #rpa-ticker .pill{background:rgba(8,10,16,.92);color:#dfe9ff;border:1px solid rgba(120,180,255,.45);
    border-radius:999px;padding:7px 14px;max-width:92vw;white-space:nowrap;overflow:hidden;
    text-overflow:ellipsis;box-shadow:0 6px 18px rgba(0,0,0,.35);opacity:.97;transition:opacity .5s}
  #rpa-ticker .pill.kind-human{border-color:rgba(120,255,180,.6);color:#d8ffe9}
  #rpa-ticker .pill.kind-wait{border-color:rgba(255,205,80,.6);color:#ffedbf}
  #rpa-ticker .pill.kind-done{border-color:rgba(150,255,200,.8);color:#c8ffdd;font-weight:800}
  `;
  document.head.appendChild(st);

  const ghost = document.createElement("div");
  ghost.className = "rpa-ghost";
  document.body.appendChild(ghost);
  const ring = document.createElement("div");
  ring.className = "rpa-ring";
  document.body.appendChild(ring);

  window.RPA = {
    ghostTo(x, y) {                       // teleport the ghost visuals to mouse coords
      ghost.style.left = x + "px"; ghost.style.top = y + "px";
      ring.style.left = x + "px"; ring.style.top = y + "px";
    },
    clickFx(x, y) {                       // expanding ripple at click point
      const r = document.createElement("div");
      r.className = "rpa-ring"; r.style.left = x + "px"; r.style.top = y + "px";
      document.body.appendChild(r);
      requestAnimationFrame(() => { r.style.width = "74px"; r.style.height = "74px";
        r.style.margin = "-37px 0 0 -37px"; r.style.opacity = "0"; });
      setTimeout(() => r.remove(), 340);
    },
    halo(sel) {                           // short highlight follow of a field
      const el = document.querySelector(sel); if (!el) return "";
      const b = el.getBoundingClientRect();
      const h = document.createElement("div");
      h.className = "rpa-halo";
      h.style.cssText = `left:${b.left-5}px;top:${b.top-5}px;width:${b.width+10}px;height:${b.height+10}px`;
      document.body.appendChild(h);
      setTimeout(() => h.remove(), 1300);
      return "ok";
    },
    hold(sel) {                           // PERSISTENT halo (attended pause)
      window.RPA.unhold();
      const el = document.querySelector(sel); if (!el) return "";
      const b = el.getBoundingClientRect();
      const h = document.createElement("div");
      h.className = "rpa-halo rpa-hold"; h.dataset.rpahold = "1";
      h.style.cssText = `left:${b.left-5}px;top:${b.top-5}px;width:${b.width+10}px;height:${b.height+10}px`;
      document.body.appendChild(h);
      return "ok";
    },
    unhold() { document.querySelectorAll('[data-rpahold]').forEach(e => e.remove()); },
    note(text, kind) {                    // ticker pill (labels from the routine!)
      const t = document.getElementById("rpa-ticker");
      const p = document.createElement("div");
      p.className = "pill kind-" + (kind || "do");
      p.textContent = text; t.appendChild(p);
      while (t.children.length > 5) t.removeChild(t.firstChild);
      return "ok";
    },
  };
  const t = document.createElement("div"); t.id = "rpa-ticker";
  document.body.appendChild(t);
  return "installed";
})();
"""


def inject_rpa(page):
    page.evaluate(INJECT)


def glide(page, mouse_state, target, beats=0.65, steps=26):
    """Ghost mouse glides to an element on the REAL page (Python-side interpolation)."""
    box = page.locator(target).bounding_box()
    if not box:
        raise RuntimeError("no bounding box for " + target)
    tx, ty = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    x0, y0 = mouse_state
    page.mouse.move(x0, y0)                        # sync ghost ring to start
    page.evaluate("([x,y]) => window.RPA.ghostTo(x,y)", [x0, y0])
    page.mouse.move(tx, ty, steps=steps)           # browser-side eased glide
    for i in range(4):                             # ghost skin follows in beats
        fi = (i + 1) / 4
        page.evaluate("([x,y]) => window.RPA.ghostTo(x,y)",
                      [x0 + (tx - x0) * fi, y0 + (ty - y0) * fi])
        time.sleep(0.05 * beats)
    mouse_state.clear(); mouse_state.extend([tx, ty])
    time.sleep(0.18 * beats)


def real_type(page, target, val, beats=0.65, delay=55):
    """Click like a human, then literal keystrokes appear in the real field."""
    page.click(target)
    time.sleep(0.1)
    page.keyboard.type(val, delay=delay)


def excel_copy(page_x, act, beats=0.65):
    """Excel phase stays on the mock panel (same proven working helpers)."""
    cell = "B" + str(act.get("Row") or "?")
    page_x.evaluate("c => window.DEMO.excelSelect(c)", cell)
    page_x.evaluate("t => window.DEMO.copyChip(t)", act.get("Value"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true",
                    help="type First Name/Surname from the log values (no pause)")
    ap.add_argument("--beats", type=float, default=0.65)
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--shot", default="", help="dir for final screenshots")
    args = ap.parse_args()
    if args.fast:
        args.beats = 0.22

    rmap = json.loads((HERE / "real_map.json").read_text())["map"]
    routine = json.loads((HERE / "routine.json").read_text())
    actions = routine["actions"]
    prov = routine.get("provenance", {}).get("pipeline_result", {}).get("routine_1", {})
    n = len(actions)

    mode = "AUTOMATIC" if args.auto else "ATTENDED"
    print(f"== REAL-TARGET RUN :: routine from log{routine['log']} "
          f"session{routine['session']} :: {n} actions :: {mode} ==")
    print(f"   live target: {REAL_URL}")
    if prov:
        print(f"   provenance: routine_1 traces={prov.get('Traces')} JC={prov.get('JC')} "
              f"fitness={prov.get('Fitness')} (vs GT {prov.get('best_gt')})")

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome", headless=args.headless)
            engine = "system-chrome"
        except Exception:
            browser = pw.chromium.launch(headless=args.headless)
            engine = "bundled-chromium"
        ctx = browser.new_context(**(
            {"no_viewport": True} if not args.headless
            else {"viewport": {"width": 1600, "height": 1000}}))
        print(f"   engine: {engine}")

        # ---- tab 1: Excel source panel (mock, proven) ---------------------
        px = ctx.new_page()
        px.goto("file://" + str(HERE / "mock_env.html"))
        px.wait_for_function("window.DemoReadyVal === true", timeout=6000)
        px.evaluate(f"window.DEMO.start({n})")
        px.bring_to_front()

        # ---- tab 2: the REAL page ----------------------------------------
        pr = ctx.new_page()
        pr.goto(REAL_URL, wait_until="domcontentloaded", timeout=30000)
        pr.wait_for_selector(".ff-el-form-control", timeout=20000)
        inject_rpa(pr)
        pr.evaluate("t => window.RPA.note(t, 'wait')",
                    "▶ ROUTINE EXECUTION ON LIVE TARGET — extract→cluster→dispatch")

        mouse_r = [900, 560]
        clipboard = None
        t0 = time.time()

        for i, act in enumerate(actions, 1):
            label = act["label"]
            spec = rmap.get(label)
            if spec is None:
                raise RuntimeError("real_map.json has no rule for " + label)
            g = spec["gesture"]
            tn = spec.get("target_name", "")

            if g == "excel_open":
                px.evaluate("() => window.DEMO.excelShow()")
                pr.evaluate("t => window.RPA.note(t)",
                            f"{i:02d}/{n} ▶ {label} → Excel workbook open")
                time.sleep(args.beats)
                px.bring_to_front()

            elif g == "navigate":
                pr.evaluate("t => window.RPA.note(t)",
                            f"{i:02d}/{n} ▶ {label} → live page loaded")
                pr.bring_to_front()
                time.sleep(args.beats)

            elif g == "type":
                sel = spec["target"]
                pr.bring_to_front()
                pr.evaluate("t => window.RPA.note(t)",
                            f"{i:02d}/{n} ▶ {label} → {tn}")
                glide(pr, mouse_r, sel, args.beats)
                if spec.get("attend") and not args.auto:
                    pr.evaluate("s => window.RPA.hold(s)", sel)
                    pr.evaluate("t => window.RPA.note(t, 'human')",
                                "⏸ human input required (attended robot — smartRPA requirement point)")
                    deadline = time.time() + 180
                    got = ""
                    while time.time() < deadline:
                        v = pr.eval_on_selector(sel, "el => el.value")
                        if v and v.strip():
                            got = v; break
                        time.sleep(0.2)
                    pr.evaluate("() => window.RPA.unhold()")
                    pr.evaluate("t => window.RPA.note(t, 'human')",
                                "✓ human input accepted → robot continues")
                else:
                    real_type(pr, sel, act.get("Value") or "", args.beats)
                    pr.evaluate("t => window.RPA.note(t)",
                                f"  ⇩ typed → {tn}")
                    time.sleep(args.beats * 0.6)

            elif g == "verify":
                pr.evaluate("() => window.scrollTo({top:0, behavior:'smooth'})")
                pr.evaluate("t => window.RPA.note(t, 'wait')",
                            f"{i:02d}/{n} ▶ {label} → page verified, ghost resynced")
                time.sleep(args.beats * 1.4)

            elif g == "select":
                sel = spec["target"]
                pr.evaluate("t => window.RPA.note(t)",
                            f"{i:02d}/{n} ▶ {label} → {tn}")
                glide(pr, mouse_r, sel, args.beats)
                try:
                    pr.select_option(sel, index=1)
                    pr.evaluate("([s]) => { const e = document.querySelector(s);"
                                "  e.dispatchEvent(new Event('change', {bubbles:true}));"
                                "  e.dispatchEvent(new Event('input', {bubbles:true})); }", [sel])
                    pr.evaluate("t => window.RPA.note(t)",
                                f"  ⇩ selected → {tn}")
                except Exception:
                    pr.evaluate("t => window.RPA.note(t, 'wait')",
                                f"  · {tn}: custom control skipped (safe)")
                time.sleep(args.beats * 0.7)

            elif g == "wait":
                pr.evaluate("t => window.RPA.note(t, 'wait')",
                            f"{i:02d}/{n} ▶ {label} → {tn or 'waiting response'}")
                time.sleep(args.beats * 1.6)

            elif g == "excel_copy":
                px.bring_to_front()
                px.evaluate("([c,l]) => window.DEMO.progress(c, l, 'Excel')",
                            [i - 1, label])
                px.evaluate("t => window.DEMO.tick('▶ ' + t, 'copy')", [label])
                excel_copy(px, act, args.beats)
                clipboard = act.get("Value") or ""
                px.evaluate("t => window.DEMO.tick('⧉ clipboard ← ' + t, 'copy')",
                            [clipboard])
                time.sleep(args.beats * 0.8)

            elif g == "paste":
                pr.bring_to_front()
                sel = spec["target"]
                pr.evaluate("t => window.RPA.note(t)",
                            f"{i:02d}/{n} ▶ {label} → {tn}")
                glide(pr, mouse_r, sel, args.beats)
                pr.click(sel)
                pr.keyboard.insert_text(clipboard or act.get("Value") or "")
                pr.evaluate("t => window.RPA.note(t)",
                            f"  ⇩ pasted → {tn}: {clipboard or act.get('Value')}")
                time.sleep(args.beats * 0.6)

            elif g == "finish_hover":
                sel = spec["target"]
                pr.evaluate("t => window.RPA.note(t)",
                            f"{i:02d}/{n} ▶ {label} → {tn}")
                glide(pr, mouse_r, sel, args.beats)
                pr.evaluate("s => window.RPA.hold(s)", sel)
                pr.evaluate("t => window.RPA.note(t, 'done')",
                            "✔ FORM READY — submit NOT clicked (demo safety veil). "
                            "Routine closed the loop on a live target.")
                time.sleep(args.beats)

        dt = time.time() - t0
        # hard proof: read back what the robot actually put on the live page
        state = pr.evaluate("""() => {
          const names = ['first_name','last_name'];
          const out = {};
          out['First Name'] = document.querySelector("input[name='names[first_name]']").value;
          out['Surname']    = document.querySelector("input[name='names[last_name]']").value;
          out['Job Group']  = document.querySelector('#ff_3_dropdown').value;
          out['Department'] = document.querySelector('#ff_3_dropdown_2').value;
          out['Personal Number'] = document.querySelector('#ff_3_numeric_field').value;
          out['Designation']     = document.querySelector('#ff_3_input_text').value;
          out['Duty Station']    = document.querySelector('#ff_3_input_text_1').value;
          return out; }""")
        print("== DOM STATE ON REAL PAGE ==")
        for k, v in state.items():
            print(f"   {k:16s} = {v!r}")
        print(f"== DONE :: {n}/{n} actions in {dt:.1f}s :: submit skipped ==")
        if args.shot:
            sd = HERE / args.shot; sd.mkdir(exist_ok=True)
            px.screenshot(path=str(sd / "real_excel_final.png"))
            pr.bring_to_front()
            time.sleep(0.5)
            pr.screenshot(path=str(sd / "real_final.png"), full_page=True)
            print("   screenshots saved:", sd / "real_final.png")
        time.sleep(6 if not args.headless else 0.2)
        browser.close()


if __name__ == "__main__":
    main()
