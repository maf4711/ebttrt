#!/usr/bin/env bash
# Dispatch a Grok hook to scripts/ebttrl.py. Paths are relative to hooks.json.
set -euo pipefail
NAME="${1:?usage: run.sh session-start|session-end|pretool}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$(cd "$HERE/../.." && pwd)}}"
exec python3 "$ROOT/scripts/ebttrl.py" hook "$NAME"
