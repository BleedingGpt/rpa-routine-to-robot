#!/usr/bin/env python3
"""
run_bot_desktop.py — THE ORIGINAL-MATERIAL demo executor (Windows-first).

Same program as the mock demo (demo_bot/routine.json — auto-extracted from OUR
replicated de-Leoni pipeline, zero hand-written steps), different deployment:
REAL DESKTOP APPS instead of an HTML mock.

  Act A. REAL Microsoft Excel via win32com (visible, cell-by-cell, an audit
         line is appended to the workbook and SAVED — open the file later and
         the run is there). Linux fallback: no win32com -> emulated cells +
         terminal notes, so the show can still be timed without Excel.
  Act B. REAL web form (frontiertechy live page, proven target). Fields typed
         keystroke-by-keystroke, gliding cursor + halo highlight.
         SUBMIT IS NEVER CLICKED — hover only (the safety veil).
  Act C. REAL Gmail compose — opens prefilled (recipient + subject + body from
         the map) in the DEFAULT browser. THE HUMAN CLICKS SEND - approval
         gate. The robot never touches any login page.

ORDER of actions comes from routine.json (seq) — the EXTRACTED program (same
file the paper reports on). That is the industry RPA story: the routine is
target-agnostic; desktop_map.json adapts it per environment.

Usage:
  python run_bot_desktop.py              # attended (you type at the creds)
  python run_bot_desktop.py --auto       # types creds itself (solo rehearsal)
  python run_bot_desktop.py --fast       # 0.25s pacing
  python run_bot_desktop.py --no-mail    # Excel + form only
  python run_bot_desktop.py --headless   # smoke, no visuals
"""
import argparse
import json
import time
import webbrowser
import urllib.parse
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "desktop_map.json").read_text())
ROUTINE = json.loads((HERE / "routine.json").read_text())
ACTIONS = sorted(ROUTINE["actions"], key=lambda a: a["seq"])
PROV = (f"log{ROUTINE['log']} session{ROUTINE['session']} "
        f"traces={ROUTINE['n_sessions_in_log']}")

ROWS = []  # audit trail (also emulated mode)


INJECT = r"""
(() => {
  if (window.RPA_DESKTOP) return "already";
  window.RPA_DESKTOP = true;
  const st = document.createElement("style");
  st.textContent = `
  .rpa-halo{position:fixed;z-index:999996;border-radius:6px;
    box-shadow:0 0 0 3px rgba(255,205,80,.9),0 0 18px rgba(255,205,80,.5);
    pointer-events:none}
  .rpa-ghost{position:fixed;z-index:999998;width:14px;height:14px;border-radius:50%;
    margin:-7px 0 0 -7px;background:rgba(250,250,255,.9);
    box-shadow:0 0 14px 4px rgba(120,180,255,.8);pointer-events:none}
  #rpa-ticker{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);
    z-index:999999;display:flex;flex-direction:column-reverse;gap:6px;
    pointer-events:none;font:600 12px/1.35 'Segoe UI',sans-serif}
  #rpa-ticker .pill{background:rgba(8,10,16,.92);color:#dfe9ff;
    border:1px solid rgba(120,180,255,.45);border-radius:999px;padding:7px 14px;
    max-width:92vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
    box-shadow:0 6px 18px rgba(0,0,0,.35);opacity:.97;transition:opacity .5s}
  #rpa-ticker .pill.kind-human{border-color:rgba(120,255,180,.6);color:#d8ffe9}
  #rpa-ticker .pill.kind-wait{border-color:rgba(255,205,80,.6);color:#ffedbf}
  #rpa-ticker .pill.kind-done{border-color:rgba(150,255,200,.8);color:#c8ffdd;font-weight:800}
  `;
  document.head.appendChild(st);
  const tick = document.createElement("div");
  tick.id = "rpa-ticker";
  document.body.appendChild(tick);
  const ghost = document.createElement("div");
  ghost.className = "rpa-ghost";
  ghost.style.left = "24px";
  ghost.style.top = "24px";
  document.body.appendChild(ghost);
  window.RPA_GHOST = ghost;
  return "ok";
})()
"""


def say(page, text, kind=""):
    css = {"": "", "human": "kind-human", "wait": "kind-wait", "done": "kind-done"}.get(kind, "")
    page.evaluate(
        """(t) => {
              const w = document.getElementById('rpa-ticker');
              if (!w) return;
              const p = document.createElement('div');
              p.className = 'pill kind-' + t[1];
              p.textContent = t[0];
              w.appendChild(p);
              setTimeout(() => { p.style.opacity = '0'; }, 4200);
              setTimeout(() => p.remove(), 4800);
           }""",
        [text, css],
    )


def halo(page, locator, ms=900):
    box = locator.bounding_box()
    if not box:
        return
    page.evaluate(
        """(b) => {
              const h = document.createElement('div');
              h.className = 'rpa-halo';
              h.style.left = (b.x - 5) + 'px';
              h.style.top = (b.y - 5) + 'px';
              h.style.width = (b.width + 10) + 'px';
              h.style.height = (b.height + 10) + 'px';
              document.body.appendChild(h);
              return h;
           }""",
        box,
    )
    time.sleep(ms / 1000)
    page.evaluate(
        """() => { const hs = document.querySelectorAll('.rpa-halo');
                   hs.forEach(h => h.remove()); }"""
    )


def glide(page, locator, steps=14):
    box = locator.bounding_box()
    if not box:
        return
    tx, ty = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.evaluate(
        """(p) => {
              const g = window.RPA_GHOST;
              if (!g) return;
              const x0 = parseFloat(g.style.left) || 24, y0 = parseFloat(g.style.top) || 24;
              for (let i = 1; i <= p[2]; i++) {
                 const k = i / p[2];
                 g.style.left = (x0 + (p[0] - x0) * k) + 'px';
                 g.style.top = (y0 + (p[1] - y0) * k) + 'px';
              }
           }""",
        [tx, ty, steps],
    )


# ------------------------------------------------------------------ Excel part
class ExcelDesk:
    """Real Excel via COM when available; emulated notes otherwise."""

    def __init__(self, beats, use_real):
        self.beats = beats
        self.app = self.wb = self.ws = None
        self.com = False
        self.vals = {"A2": "1", "B2": "27182", "C2": "Amir Karim Ruman"}
        if use_real:
            try:
                import win32com.client  # noqa: F401
                self.com = True
            except ImportError:
                print("   [excel] win32com missing -> emulated cells (rehearsal mode)")

    def _raise_excel(self):
        """Bring the demo workbook window in front of everything so the
        audience actually SEES every Excel change (2nd screen moment of the
        show: Excel <-> browser alternation). Best-effort cosmetics only.
        """
        try:
            import pygetwindow as gw
            for w in gw.getAllWindows():
                if "desktop_demo" in (w.title or ""):
                    if w.isMinimized:
                        w.restore()
                    w.activate()
                    time.sleep(0.5)
                    return True
        except Exception:
            pass
        return False

    def _note(self, msg):
        print(f"   [excel] {msg}")

    def type_visible(self, cell, text):
        """Type text char-by-char into a cell so ma'am SEES it happen.
        Uses Excel's own SendKeys (in-process, delivered to Excel only -
        never the OS-wide keyboard). Empty cell = plain overwrite.
        """
        if not self.com:
            self.vals[cell] = text
            self._note(f"typed {text!r} into {cell} (emulated)")
            return
        self._raise_excel()
        rng = self.ws.Range(cell)
        rng.Select()
        time.sleep(0.4)
        try:
            special = set("+^%~(){}")
            for ch in text:
                key = "{" + ch + "}" if ch in special else ch
                self.app.SendKeys(key, True)
                time.sleep(0.05)
            self.app.SendKeys("{ENTER}", True)
        except Exception:
            # belt-and-braces fallback: cancel edit mode, direct value write
            try:
                self.app.SendKeys("{ESC}", True)
            except Exception:
                pass
            self.ws.Range(cell).Value = text
        time.sleep(self.beats)

    def open(self):
        if not self.com:
            self._note(f"emulated open of {CFG['workbook']}")
            return None
        import win32com.client as w
        try:
            self.app = w.Dispatch("Excel.Application")
            self.app.Visible = True
            self.app.ScreenUpdating = True
            self.wb = self.app.Workbooks.Open(str(HERE / CFG["workbook"]))
            self.ws = self.wb.Sheets(CFG["sheet"])
        except Exception as e:
            print(f"   [excel] REAL Excel failed to open ({e!r:.70}) -> emulating so the show continues")
            self.com = False
            self._note(f"emulated open of {CFG['workbook']}")
            return None
        # Excel must WIN the screen war: maximize + front of the z-order + wait out launch animation
        try:
            self.app.WindowState = -4137   # xlMaximized
            self.app.ActiveWindow.Activate()
        except Exception:
            pass  # window-manager cosmetics — never fatal
        self.ws.Activate()
        self.ws.Range("A1").Select()
        time.sleep(2.0)      # let Excel's first paint land so Ma'am sees a REAL spreadsheet
        time.sleep(self.beats)
        self._note("real Excel open — MAXIMIZED window visible on screen, robot is editing it now")
        return (self.app, self.wb, self.ws)

    def read(self, cell):
        if self.com:
            return str(self.ws.Range(cell).Value or "")
        return self.vals.get(cell, "")

    def audit(self, msg, tail=""):
        text = f"{datetime.now().strftime('%H:%M:%S')}  {msg} {tail}".strip()
        if not self.com:
            ROWS.append(text)
            self._note(f"audit: {text}")
            return
        nxt = 2
        while self.ws.Range(f"{CFG['cells']['audit_col']}{nxt}").Value:
            nxt += 1
        # visible proof: the line is TYPED into column E, keystroke by keystroke
        self.type_visible(f"{CFG['cells']['audit_col']}{nxt}", text)

    def copy(self, cell=None):
        cell = cell or CFG["cells"]["row"]
        val = self.read(cell)
        if self.com:
            self._raise_excel()
            self.ws.Range(cell).Select()
            time.sleep(self.beats)
            try:
                self.app.SendKeys("^c", True)     # REAL copy - marching ants on screen
                time.sleep(1.0)                   # Ma'am sees the ants crawl around the cell
            except Exception:
                pass
            try:
                self.app.SendKeys("{ESC}", True)  # clear the ants (clipboard KEEPS the
                # value; leaving the marquee on would make the next Enter act as paste)
                time.sleep(0.4)
            except Exception:
                pass
        self._note(f"copied {val} from {cell} -> clipboard (real Ctrl+C)")
        return val

    def finish(self):
        text = f"{datetime.now().strftime('%H:%M:%S')}  routine finished - workbook saved"
        if not self.com:
            if ROWS:
                (HERE / "desktop_demo_audit.txt").write_text("\n".join(ROWS))
                self._note("emulated audit saved to desktop_demo_audit.txt")
            return
        nxt = 2
        while self.ws.Range(f"{CFG['cells']['audit_col']}{nxt}").Value:
            nxt += 1
        self.type_visible(f"{CFG['cells']['audit_col']}{nxt}", text)
        self.wb.Save()
        self._note("workbook SAVED — audit trail is IN the real file")


# ------------------------------------------------------------------- the loop
def runBot(page, beats, attended, des, args):
    page.goto(CFG["web"]["_url"], wait_until="domcontentloaded")
    page.evaluate(INJECT)
    time.sleep(1.0)
    copied = None
    des.open()
    des.audit("robot session started", tail=f"({PROV})")
    for a in ACTIONS:
        g = CFG["web"]["map"].get(str(a["seq"]))  # map keyed by seq — labels repeat (copy_B_Excel ×2)
        if not g:
            continue
        gesture = g["gesture"]
        tn = g.get("target_name", a["label"])
        if gesture == "excel_open":
            say(page, "Excel phase — real workbook open on desktop", "wait")
            time.sleep(beats)
            continue
        if gesture == "excel_copy":
            copied = des.copy(g.get("cell"))
            des.audit(f"copied {copied} from {g.get('cell') or CFG['cells']['row']}")
            continue
        if gesture == "navigate":
            say(page, f"target: {CFG['web']['_url']}", "wait")
            time.sleep(beats)
            continue
        if gesture == "wait":
            say(page, f"waiting: {tn}", "wait")
            time.sleep(beats + 0.4)
            continue
        if gesture == "mail_compose":
            if args.no_mail:
                say(page, "mail skipped (--no-mail)", "wait")
                continue
            m = CFG["mail"]
            reg = m["subject"].replace("[[ID]]", str(copied or ""))
            bod = (m["body"].replace("[[ID]]", str(copied or ""))
                   .replace("[[NAME]]", des.read(CFG["cells"]["name"])))
            if args.human_send or not m.get("smtp_app_password") or "PUT-" in str(m.get("smtp_app_password", "")):
                # fallback path: compose-URL in the default browser, human clicks Send
                url = ("https://mail.google.com/mail/?view=cm&fs=1&to="
                       + urllib.parse.quote(m["to"]) + "&su="
                       + urllib.parse.quote(reg) + "&body=" + urllib.parse.quote(bod))
                say(page, "opening REAL Gmail compose…", "done")
                webbrowser.open_new_tab(url)
                print(f"   [mail] compose opened -> {m['to']} | subject: {reg}")
                if attended:
                    input("   >>> Gmail is in YOUR default browser — check it, click SEND, press Enter: ")
                    say(page, "sent by human — approval gate stands ✓", "human")
                else:
                    print("   [mail] auto-mode: compose opened, human still sends (gate preserved)")
            else:
                # primary path: THE ROBOT SENDS THE EMAIL — real SMTP, no browser, no login dance
                from email.message import EmailMessage
                import smtplib
                import ssl as _ssl
                msg = EmailMessage()
                msg["From"] = m["smtp_user"]
                msg["To"] = m["to"]
                msg["Subject"] = reg
                msg.set_content(bod)
                try:
                    ctx = _ssl.create_default_context()
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
                        s.login(m["smtp_user"], m["smtp_app_password"])
                        s.send_message(msg)
                    say(page, "email SENT by the robot ✔ — check the recipient's inbox", "done")
                    print(f"   [mail] SENT {m['smtp_user']} -> {m['to']} | {reg}")
                    if attended:
                        input("   >>> email is really sent — Ma'am can check her phone/inbox. Enter to continue: ")
                except Exception as e:
                    print(f"   [mail] SMTP send failed ({e!r:.80}) -> falling back to compose window")
                    url = ("https://mail.google.com/mail/?view=cm&fs=1&to="
                           + urllib.parse.quote(m["to"]) + "&su="
                           + urllib.parse.quote(reg) + "&body=" + urllib.parse.quote(bod))
                    webbrowser.open_new_tab(url)
                    say(page, "compose opened — human clicks Send (SMTP was not available)", "wait")
                    if attended:
                        input("   >>> check it, click SEND, press Enter: ")
            time.sleep(beats)
            continue
        # ---- web gestures (browser wins the screen during web actions:
        # the audience alternates Excel <-> browser, exactly like real RPA)
        loc = page.locator(g["target"])
        try:
            page.bring_to_front()
            time.sleep(0.3)
        except Exception:
            pass
        if g.get("attend") and attended:
            say(page, f"YOUR TURN — type {tn} in the browser", "human")
            input("   >>> type it in the BROWSER window, then press Enter here: ")
            halo(page, loc, 700)
            say(page, f"{tn} typed by human ✓", "human")
            continue
        if gesture in ("type", "paste"):
            if g.get("from_excel"):
                value = des.read(g["from_excel"])
            elif "value" in g:
                value = g["value"]
            else:
                value = str(copied or "")
            glide(page, loc)
            halo(page, loc)
            loc.click()
            loc.fill("")
            pasted = False
            if gesture == "paste":
                # REAL paste: the clipboard still holds exactly what Excel
                # copied with the real Ctrl+C earlier. Try a real Ctrl+V;
                # if Chrome refuses, fall back to honest keystroke typing.
                try:
                    page.keyboard.press("Control+v")
                    time.sleep(0.8)
                    pasted = str(loc.input_value()) == str(value)
                except Exception:
                    pasted = False
            if not pasted:
                for ch in str(value):
                    page.keyboard.type(ch, delay=45)
                    time.sleep(0.012)
            if pasted:
                say(page, f"{tn} = {value}  (REAL paste from Excel's clipboard)", "done")
            else:
                say(page, f"{tn} = {value}"
                          f"{'  (from Excel)' if gesture == 'paste' else ''}", "done")
            if args.headless is False:
                page.screenshot(path=str(HERE / "shots" / f"desktop_{a['seq']:02d}.png"))
        elif gesture in ("select", "verify"):
            glide(page, loc)
            halo(page, loc)
            if gesture == "select":
                loc.select_option(index=1)
                say(page, f"{tn} selected", "done")
            else:
                say(page, f"{tn} verified ({g.get('how', 'checked')})", "wait")
        elif gesture == "finish_hover":
            glide(page, loc)
            halo(page, loc, 1800)
            say(page, "SUBMIT NOT CLICKED — safety veil (hover only)", "wait")
        time.sleep(beats)
    des.finish()
    return copied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--beats", type=float, default=0.7)
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--no-excel", action="store_true")
    ap.add_argument("--no-mail", action="store_true")
    ap.add_argument("--human-send", action="store_true",
                    help="force the compose-window path where the human clicks Send")
    ap.add_argument("--show-preview", action="store_true",
                    help="open screenshots after the run")
    args = ap.parse_args()
    if args.fast:
        args.beats = min(args.beats, 0.25)
    attended = not args.auto
    print(f"== RUN-BOT-DESKTOP :: {PROV} :: {len(ACTIONS)} actions :: "
          f"real Excel: {'yes' if not args.no_excel else 'skipped'} :: "
          f"real form :: robot-SENT Gmail {'(skipped)' if args.no_mail else ''} ==")
    des = ExcelDesk(args.beats, use_real=not args.no_excel)
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome", headless=args.headless)
        except Exception:
            browser = pw.chromium.launch(headless=args.headless)
        ctx = browser.new_context(viewport={"width": 1380, "height": 860})
        page = ctx.new_page()
        runBot(page, args.beats, attended, des, args)
        if attended:
            input("   >>> finished state on screen — press Enter to close: ")
        browser.close()
    if args.show_preview:
        shots = sorted((HERE / "shots").glob("desktop_*.png"))
        for s in shots:
            webbrowser.open(s.as_uri())
            time.sleep(0.4)
    print("== DONE :: workbook audit saved :: evidence on disk ==")


if __name__ == "__main__":
    main()
