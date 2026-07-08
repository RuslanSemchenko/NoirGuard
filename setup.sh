#!/usr/bin/env bash
set -e

echo "========================================"
echo "  NoirGuard - DevSecOps Auditor"
echo "========================================"
echo ""

# ---------------------------------------------------------------
# 1. Find Python
# ---------------------------------------------------------------
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python not found. Install Python 3.14+ from https://python.org"
    exit 1
fi
echo "[OK] Python: $PYTHON"

# ---------------------------------------------------------------
# 2. Create venv if needed
# ---------------------------------------------------------------
if [ ! -f ".venv/bin/python" ]; then
    echo "[..] Creating virtual environment..."
    "$PYTHON" -m venv .venv
    echo "[OK] Virtual environment created"
fi
VENV_PY="$(cd "$(dirname "$0")" && pwd)/.venv/bin/python"

# ---------------------------------------------------------------
# 3. Install dependencies
# ---------------------------------------------------------------
echo "[..] Installing dependencies..."
"$VENV_PY" -m pip install -r requirements.txt pylint -q
echo "[OK] Dependencies installed"

# ---------------------------------------------------------------
# 4. Set environment variables
#    TIP: Create a copy named 'setup_private.sh' with your keys
#         setup_private.sh is already in .gitignore
# ---------------------------------------------------------------
echo ""
echo "API keys not set yet."
echo "You can:"
echo "  a) Enter keys now (they persist for this terminal session)"
echo "  b) Create a .env file and re-run"
echo "  c) cp setup.sh setup_private.sh, fill in keys (gitignored)"
echo ""

read -rp "QWEN_API_KEY (press Enter to skip): " QWEN_API_KEY
[ -z "$QWEN_API_KEY" ] && QWEN_API_KEY="not_set"

read -rp "QWEN_BASE_URL (Enter for default): " QWEN_BASE_URL
[ -z "$QWEN_BASE_URL" ] && QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"

read -rp "GITHUB_TOKEN (press Enter to skip): " GITHUB_TOKEN
[ -z "$GITHUB_TOKEN" ] && GITHUB_TOKEN="not_set"

export QWEN_API_KEY QWEN_BASE_URL GITHUB_TOKEN

echo ""
echo "========================================"
echo "  Ready. Available commands:"
echo "========================================"
echo "  $VENV_PY run_audit.py              - Quick audit test"
echo "  ./test_pr.bat                      - Full PR test (Windows)"
echo "  $VENV_PY pr_audit.py owner/repo N  - Audit PR #N"
echo "  uvicorn app.main:app --reload      - Web server"
echo ""
echo "Example: $VENV_PY pr_audit.py RuslanSemchenko/NoirGuard 1"
echo ""
