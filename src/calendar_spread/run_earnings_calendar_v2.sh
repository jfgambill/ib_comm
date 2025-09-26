#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Run the earnings-calendar scraper/recommendation pipeline with IB Gateway.
# Expects a Python virtual-environment named "venv" in /home/me/src/ib_comm.
# ---------------------------------------------------------------------------

set -euo pipefail   # fail on first error, unset var, or pipe error

## Paths ---------------------------------------------------------------------
BASE_DIR="/home/me/src/ib_comm"
VENV_DIR="${BASE_DIR}/venv"
RUN_DIR="${BASE_DIR}/src/calendar_spread"
SCRIPT="${RUN_DIR}/earnings_calendar_v5.py"  # Updated to use v2 script
IB_GATEWAY_DIR="/home/me/Jts"  # Adjust this path to your IB Gateway installation
IB_PORT=4001  # Default IB Gateway port for live trading (use 4002 for paper)

## Functions -----------------------------------------------------------------
start_ib_gateway() {
    echo "Starting IB Gateway..."
    
    # Check if IB Gateway is already running
    if pgrep -f "ibgateway" > /dev/null; then
        echo "IB Gateway is already running"
        return 0
    fi
    
    # Start IB Gateway in the background
    # Note: You may need to adjust this command based on your IB Gateway installation
    cd "$IB_GATEWAY_DIR"
    nohup ./ibgateway &
    
    echo "IB Gateway started, waiting for initialization..."
    sleep 45  # Give IB Gateway time to start up
}

check_ib_connection() {
    echo "Checking IB Gateway connection..."
    
    cd "$RUN_DIR"
    source "${VENV_DIR}/bin/activate"
    
    # Create a simple connection test script
    python3 -c "
import asyncio
import sys
sys.path.append('$BASE_DIR/src')
from ib_async import IB

async def test_connection():
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', $IB_PORT, clientId=999)
        print('✓ IB Gateway connection successful')
        ib.disconnect()
        return True
    except Exception as e:
        print(f'✗ IB Gateway connection failed: {e}')
        return False

result = asyncio.run(test_connection())
sys.exit(0 if result else 1)
"
    
    return $?
}

wait_for_ib_connection() {
    echo "Waiting for IB Gateway to accept connections..."
    
    local max_attempts=12  # 12 attempts = 2 minutes
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        echo "Connection attempt $attempt of $max_attempts..."
        
        if check_ib_connection; then
            echo "✓ IB Gateway is ready!"
            return 0
        fi
        
        if [ $attempt -lt $max_attempts ]; then
            echo "Waiting 10 seconds before next attempt..."
            sleep 10
        fi
        
        ((attempt++))
    done
    
    echo "✗ Failed to connect to IB Gateway after $max_attempts attempts"
    return 1
}

cleanup() {
    echo "Cleaning up..."
    # Optional: Stop IB Gateway if we started it
    # pkill -f "ibgateway" || true
}

## Main Script ---------------------------------------------------------------
trap cleanup EXIT

echo "=== IB Gateway Earnings Calendar Pipeline ==="
echo "Date: $(date)"
echo "Target date: $(date +%F)"
echo

## Start IB Gateway if not running -------------------------------------------
start_ib_gateway

## Wait for IB Gateway to be ready -------------------------------------------
if ! wait_for_ib_connection; then
    echo "ERROR: Could not establish connection to IB Gateway"
    echo "Please check:"
    echo "1. IB Gateway is installed in $IB_GATEWAY_DIR"
    echo "2. You are logged into IB Gateway"
    echo "3. API connections are enabled in IB Gateway settings"
    echo "4. Port $IB_PORT is correct (4001=live, 4002=paper)"
    exit 1
fi

## Activate venv -------------------------------------------------------------
cd "$BASE_DIR"
source "${VENV_DIR}/bin/activate"
cd "$RUN_DIR"

## Run the earnings calendar script -----------------------------------------
echo "Running earnings calendar script for $(date +%F)..."
python "$SCRIPT" "$(date +%F)" --port $IB_PORT

echo "✓ Earnings calendar pipeline completed successfully"