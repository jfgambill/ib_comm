#!/bin/bash
# ---------------------------------------------------------------------------
# Fetch Jungle Rock program emails from Gmail
# Looks for emails from noreply@junglerock.com with "Program" in subject
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
echo "Fetching Jungle Rock program emails..."
echo "Looking for emails from: noreply@junglerock.com"
echo "Subject contains: Program"
echo "Only unread emails: Yes"
echo ""

# Change to src directory so imports work properly
cd "$SRC_DIR"

python "email/gmail_reader.py" \
    --sender "noreply@junglerock.com" \
    --subject "Program" \
    --unread

echo ""
echo "Jungle Rock email fetch completed at $(date)"