#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Uso:
  ./run_dry_run.sh

Arranca el bot en simulacion pura.

Que hace:
  - No lee Sesame real.
  - No escribe en Sesame.
  - Usa BOT_FAKE_STATE o el estado simulado guardado en dry_state.json.
  - Sirve para probar Telegram y la maquina de estados sin riesgo.

Comandos utiles:
  BOT_FAKE_STATE=working ./run_dry_run.sh
  Ctrl+C para parar si corre en terminal.
EOF
  exit 0
fi

export BOT_DRY_RUN=1
export BOT_ALLOW_REAL=0
export BOT_TEST_EMPLOYEE_ID="${BOT_TEST_EMPLOYEE_ID:-demo}"

python3 telegram_bot.py
