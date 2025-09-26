#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Run the earnings-calendar scraper/recommendation pipeline.
# Expects a Python virtual-environment named “venv” in /home/me/src/ib_comm.
# ---------------------------------------------------------------------------

set -euo pipefail   # fail on first error, unset var, or pipe error

## Paths ---------------------------------------------------------------------
BASE_DIR="/home/me/src/ib_comm"
VENV_DIR="${BASE_DIR}/venv"
RUN_DIR="${BASE_DIR}/src/calendar_spread"
SCRIPT="${RUN_DIR}/earnings_calendar_v5.py"

## Activate venv -------------------------------------------------------------
cd "$BASE_DIR"
source "${VENV_DIR}/bin/activate"
cd "$RUN_DIR"

## Run the script for *today’s* date -----------------------------------------
python "$SCRIPT" "$(date +%F)"
