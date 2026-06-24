#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Uso:
  ./run_real_state_dry_actions.sh

Arranca el bot en modo seguro de preproduccion.

Que hace:
  - Lee estado real de Sesame para /estado.
  - Lee fichajes reales de hoy para /hoy.
  - Comprueba sesion real con /sesion.
  - NO ejecuta fichajes reales: fichar/pausar siguen simulados.

Requisitos:
  - config.json con telegram_token.
  - config.json con usid o sesame_token, csid, esid, employee_id.
  - config.json con authorized_chat_ids.

Comandos utiles:
  python3 check_config.py
  python3 probe_sesame_state.py
  Ctrl+C para parar si corre en terminal.

Para dejarlo siempre encendido:
  ver docs/always-on.md
EOF
  exit 0
fi

export BOT_DRY_RUN=0
export BOT_ALLOW_REAL=0

python3 telegram_bot.py
