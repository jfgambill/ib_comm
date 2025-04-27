#!/bin/bash
# email_checker.sh - Checks for program emails with retry logic

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VENV_PATH="/home/me/src/ib_comm/venv"
PYTHON_SCRIPT="$SCRIPT_DIR/protonmail_reader.py"
SENDER="noreply@junglerock.com"
SUBJECT="Program"
MAX_ATTEMPTS=8  # Will try for about 8 minutes (from 3:52pm to 4:00pm)
WAIT_TIME=60    # Wait 60 seconds between attempts
CONFIG_FILE="$SCRIPT_DIR/config.ini"

# Get current date in YYYY-MM-DD format
TODAY=$(date +"%Y-%m-%d")

# Function to check if python script is in expected location
check_script() {
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        echo "Error: Python script not found at $PYTHON_SCRIPT"
        exit 1
    fi
}

# Function to check if config file exists
check_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Error: Config file not found at $CONFIG_FILE"
        exit 1
    fi
}

# Function to check if the virtual environment exists
check_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        echo "Error: Virtual environment not found at $VENV_PATH"
        exit 1
    fi
    
    if [ ! -f "$VENV_PATH/bin/activate" ]; then
        echo "Error: Virtual environment activation script not found"
        exit 1
    fi
}

# Function to run the email check with virtual environment
run_email_check() {
    echo "Running email check for $TODAY..."
    source "$VENV_PATH/bin/activate"
    python "$PYTHON_SCRIPT" --all --sender "$SENDER" --subject "$SUBJECT" --date-from "$TODAY" --notify --exit-code --config "$CONFIG_FILE"
    local result=$?
    deactivate
    return $result
}

# Main function with retry logic
main() {
    check_script
    check_config
    check_venv
    
    echo "Starting email check at $(date)"
    attempt=1
    
    while [ $attempt -le $MAX_ATTEMPTS ]; do
        echo "Attempt $attempt of $MAX_ATTEMPTS"
        
        # Run the email check
        run_email_check
        result=$?
        
        # If emails were found (exit code 0), we're done
        if [ $result -eq 0 ]; then
            echo "Success: Emails found and processed!"
            exit 0
        fi
        
        # If we've reached the maximum attempts, send a final notification
        if [ $attempt -eq $MAX_ATTEMPTS ]; then
            echo "Maximum attempts reached. No emails found."
            # Final notification will have been sent by the Python script
            exit 1
        fi
        
        # Increment attempt counter and wait
        ((attempt++))
        echo "No emails found yet. Waiting $WAIT_TIME seconds before next attempt..."
        sleep $WAIT_TIME
    done
}

# Run the main function
main
