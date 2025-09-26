#!/bin/bash
# ---------------------------------------------------------------------------
# Fetch OQuants "Top Plays" emails from Gmail
# Looks for emails from daily@mail.oquants.com with "Top Plays" in subject
# ---------------------------------------------------------------------------

set -euo pipefail   # fail on first error, unset var, or pipe error

## Paths ---------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="${REPO_ROOT}/src"
EMAIL_DIR="${SRC_DIR}/email"
SCRIPT_PATH="${EMAIL_DIR}/gmail_reader.py"

## Check if script exists ----------------------------------------------------
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: gmail_reader.py not found at $SCRIPT_PATH"
    exit 1
fi

## Check if Python virtual environment is activated -------------------------
if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "Warning: No virtual environment detected."
    echo "Consider activating your venv first:"
    echo "  source /path/to/your/venv/bin/activate"
    echo ""
fi

## Run the Gmail reader ------------------------------------------------------
echo "Fetching OQuants Top Plays emails..."
echo "Looking for emails from: daily@mail.oquants.com"
echo "Subject contains: Top Plays"
echo "Only unread emails: Yes"
echo ""

# Change to src directory so imports work properly
cd "$SRC_DIR"

python "email/gmail_reader.py" \
    --sender "daily@mail.oquants.com" \
    --subject "Top Plays" \
    --unread

echo ""
echo "OQuants email fetch completed at $(date)"