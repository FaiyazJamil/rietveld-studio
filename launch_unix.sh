#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
export GSASII_PATH="$PWD/.engine/GSAS-II"
exec .venv/bin/python -m rietveld_studio "$@"

