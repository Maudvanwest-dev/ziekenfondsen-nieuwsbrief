#!/usr/bin/env bash
# Registreer een wekelijkse cron job: elke maandag om 08:00.
# Gebruik: bash setup_cron.sh
#
# Vereisten:
#   - .env staat in dezelfde map als dit script
#   - python3 en de packages uit requirements.txt zijn geïnstalleerd

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(command -v python3)"
ENV_FILE="$SCRIPT_DIR/.env"
MAIN_SCRIPT="$SCRIPT_DIR/nieuwsbrief.py"
LOG_FILE="$SCRIPT_DIR/nieuwsbrief.log"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[FOUT] $ENV_FILE niet gevonden. Maak het aan op basis van .env.example."
  exit 1
fi

# Cron-expressie: minuut uur dag-van-maand maand dag-van-week
# 0 8 * * 1  =  elke maandag om 08:00
CRON_EXPR="0 8 * * 1"

# source .env inline zodat de cron job de variabelen leest
CRON_CMD="cd \"$SCRIPT_DIR\" && set -a && source \"$ENV_FILE\" && set +a && \"$PYTHON\" \"$MAIN_SCRIPT\" >> \"$LOG_FILE\" 2>&1"
CRON_LINE="$CRON_EXPR $CRON_CMD"

if crontab -l 2>/dev/null | grep -qF "nieuwsbrief.py"; then
  echo "Een cron job voor nieuwsbrief.py bestaat al:"
  crontab -l | grep "nieuwsbrief.py"
else
  (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
  echo "Cron job toegevoegd:"
  echo "  $CRON_LINE"
  echo ""
  echo "Controleer met: crontab -l"
fi
