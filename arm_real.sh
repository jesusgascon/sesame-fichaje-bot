#!/usr/bin/env bash
set -euo pipefail

# Arma el TERCER factor del camino real: crea el fichero ENABLE_REAL con la hora
# actual. Abre una ventana (BOT_ENABLE_REAL_TTL_SECONDS, por defecto 3600s) tras
# la cual el camino real vuelve a quedar desarmado aunque queden las env vars.
#
# Esto NO ficha por sí solo: el POST real exige ADEMÁS BOT_DRY_RUN=0,
# BOT_ALLOW_REAL=1 y un chat vinculado por OTP. Úsalo solo para la prueba
# controlada y con OK explícito.
cd "$(dirname "$0")"

if [[ "${1:-}" == "off" ]]; then
  rm -f ENABLE_REAL
  echo "Camino real DESARMADO (ENABLE_REAL borrado)."
  exit 0
fi

touch ENABLE_REAL
chmod 600 ENABLE_REAL
ttl="${BOT_ENABLE_REAL_TTL_SECONDS:-3600}"
echo "Camino real ARMADO durante ${ttl}s. Para desarmar antes: ./arm_real.sh off"
