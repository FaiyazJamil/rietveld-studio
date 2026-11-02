#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
rietveld_python="${RIETVELD_PYTHON:-python3.11}"
"$rietveld_python" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install 'numpy==2.2.6' 'PyCifRW>=4.4' gitpython
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/bootstrap_engine.py
.venv/bin/python scripts/generate_demo.py --destination examples/synthetic_nacl --gsas-path .engine/GSAS-II
echo 'Ready. Start with ./launch_unix.sh'

