#!/bin/bash

# Script to run the Mokuro Translator with debug logging

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "No virtual environment found. Running with system Python..."
fi

# Set Python path to include the src directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Ensure DISPLAY is set for GUI applications (important for some systems)
if [ -z "$DISPLAY" ] && [ -n "$XDG_SESSION_TYPE" ]; then
    export DISPLAY=:0
fi

# Run the application with debug logging
echo "Starting Mokuro Translator with debug logging..."
echo "Debug output will be shown in this terminal."
echo "The GUI window should open shortly..."
echo "----------------------------------------"

cd src/ll_ocl_comics
python main.py

echo "----------------------------------------"
echo "Script finished."
