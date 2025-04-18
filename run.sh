#!/usr/bin/env bash
#
# Launch the Streamlit app from *wherever* you call this script.

# Absolute path to the directory the script lives in:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Kick off Streamlit
streamlit run "${SCRIPT_DIR}/app/0_Updates.py"