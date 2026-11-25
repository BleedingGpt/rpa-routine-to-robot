#!/usr/bin/env bash
# DOUBLE-CLICK / one-command launcher for the live demo.
#
#   ./LAUNCH.sh                 mock-target demo: attended (pauses at the two
#                               credential fields; human types, robot continues)
#   ./LAUNCH.sh --auto          fully automatic mock-target run
#   ./LAUNCH.sh --fast          quick rehearsal (0.22s beats)
#   ./LAUNCH.sh --real          REAL-TARGET demo: same routine.json drives the
#                               live webpage https://demoform.frontiertechy.com/form-a/
#                               (Excel panel still the routine's data source;
#                                Submit is NEVER clicked - safety veil)
#
cd "$(dirname "$0")"

if [ "$1" = "--real" ]; then
  shift
  exec .venv/bin/python run_bot_real.py "$@"
fi

exec .venv/bin/python run_bot.py "$@"
