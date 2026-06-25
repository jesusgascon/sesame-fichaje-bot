#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Uso:
  ./run_real.sh

Arranca el bot en MODO REAL. ATENCION: puede crear fichajes reales en Sesame.

Un fichaje real solo ocurre si se dan TODOS estos factores:
  - BOT_DRY_RUN=0 y BOT_ALLOW_REAL=1     (los pone este script)
  - fichero ENABLE_REAL vigente           (crealo con ./arm_real.sh)
  - el chat vinculado por OTP             (/vincular en Telegram)
  - confirmacion SI en las acciones delicadas

Sin ENABLE_REAL o sin binding, el bot NO ficha (lanza un error controlado).
Parada de emergencia: "kill_switch": true en config.json (se relee en caliente),
o Ctrl+C, o systemctl --user stop sesame-fichaje-bot.service.

Ventana del 3er factor: BOT_ENABLE_REAL_TTL_SECONDS (por defecto 3024000 = 35 dias).
Ver docs/security.md y docs/production-runbook.md.
EOF
  exit 0
fi

cd "$(dirname "$0")"
./secure_perms.sh >/dev/null 2>&1 || true

export BOT_DRY_RUN=0
export BOT_ALLOW_REAL=1
export BOT_ENABLE_REAL_TTL_SECONDS="${BOT_ENABLE_REAL_TTL_SECONDS:-3024000}"   # 35 dias

if [[ ! -f ENABLE_REAL ]]; then
  echo "AVISO: no existe ENABLE_REAL -> el bot responde y lee, pero NO fichara real."
  echo "       Para armar el camino real: ./arm_real.sh"
fi

echo "Arrancando en MODO REAL (3er factor por ENABLE_REAL; binding OTP requerido)."
python3 telegram_bot.py
