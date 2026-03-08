#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# BP Executive Assistant – Setup Script
# Run this once on your Linux server to get everything ready.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[setup]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
error()   { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

# ── 1. Python check ────────────────────────────────────────────────────────────
info "Checking Python version…"
python_cmd=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(sys.version_info[:2])")
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"; then
            python_cmd="$cmd"
            info "Using $cmd ($version)"
            break
        fi
    fi
done
[[ -z "$python_cmd" ]] && error "Python 3.10+ is required but not found."

# ── 2. Virtual environment ─────────────────────────────────────────────────────
if [[ ! -d ".venv" ]]; then
    info "Creating virtual environment in .venv…"
    "$python_cmd" -m venv .venv
fi
source .venv/bin/activate
info "Virtual environment activated."

# ── 3. Install dependencies ────────────────────────────────────────────────────
info "Installing Python dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
info "Dependencies installed."

# ── 4. Environment file ────────────────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
    info "Creating .env from template…"
    cp .env.example .env
    warn "IMPORTANT: Edit .env and fill in your API tokens before running the assistant."
else
    info ".env already exists – skipping copy."
fi

# ── 5. Config directory ────────────────────────────────────────────────────────
mkdir -p config logs
info "Directories created: config/ logs/"

# ── 6. Google OAuth setup hint ─────────────────────────────────────────────────
echo ""
info "─── Google OAuth Setup ──────────────────────────────────────────"
echo "  1. Go to https://console.cloud.google.com/"
echo "  2. Create a project, enable Gmail API and Google Tasks API."
echo "  3. Create OAuth 2.0 Desktop credentials."
echo "  4. Download the JSON file → save as: config/google_credentials.json"
echo "  5. Run the auth flow once (requires a browser on first run):"
echo "       source .venv/bin/activate"
echo "       python src/integrations/gmail.py --auth"
echo ""

# ── 7. Cron job ────────────────────────────────────────────────────────────────
info "─── Cron Job Installation ───────────────────────────────────────"
PYTHON_PATH="$SCRIPT_DIR/.venv/bin/python"
SCRIPT_PATH="$SCRIPT_DIR/src/morning_brief.py"
CRON_LINE="0 4 * * 1-5 cd $SCRIPT_DIR && $PYTHON_PATH $SCRIPT_PATH >> $SCRIPT_DIR/logs/cron.log 2>&1"

echo ""
echo "  Add the following line to your crontab (run 'crontab -e'):"
echo ""
echo "    $CRON_LINE"
echo ""

read -rp "  Install cron job automatically now? [y/N] " install_cron
if [[ "${install_cron,,}" == "y" ]]; then
    # Check if the cron entry already exists
    if crontab -l 2>/dev/null | grep -qF "morning_brief.py"; then
        warn "Cron job already installed – skipping."
    else
        (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
        info "Cron job installed. It will run at 4:00 AM Monday–Friday."
    fi
fi

echo ""
info "Setup complete! Next steps:"
echo "  1. Edit .env with your API credentials."
echo "  2. Complete the Google OAuth flow (see instructions above)."
echo "  3. Test with: source .venv/bin/activate && python src/morning_brief.py"
