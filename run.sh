#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Navigate to the target directory relative to script location
cd "$SCRIPT_DIR/src/ll_ocl_comics"

# Activate virtual environment
source venv/bin/activate

# Run the Python application
python main.py
