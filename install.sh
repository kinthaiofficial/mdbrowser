#!/usr/bin/env bash
# Set up mdbrowser in a local virtualenv next to this script.
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -U pip >/dev/null
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
chmod +x mdbrowser
echo
echo "Done. Try:   ./mdbrowser https://example.com"
echo "Browse:      ./mdbrowser"
echo "On PATH:     sudo ln -sf \"$(pwd)/mdbrowser\" /usr/local/bin/mdbrowser"
