#!/bin/sh
set -eu
TRIPPILOT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$TRIPPILOT_ROOT/backend/.venv/bin/python" "$TRIPPILOT_ROOT/scripts/dev_v1_1.py" "$@"
