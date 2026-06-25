#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
Sesame fichaje bot - ayuda rapida

Arranques:
  ./run_dry_run.sh
      Simulacion pura. No lee ni escribe Sesame.

  ./run_real_state_dry_actions.sh
      Modo seguro recomendado. Lee Sesame real, pero no ficha real.

Comprobaciones:
  python3 check_config.py
      Revisa configuracion local sin imprimir secretos.

  python3 probe.py state
      Lee el estado real actual de Sesame.

  python3 probe.py types
      Comprueba sesion y tipos asignados.

  python3 probe.py checks
      Vuelca los checks de hoy (claves seguras).

  python3 probe.py pauses
      Busca el id de Descanso en checks existentes.

  python3 set_telegram_commands.py
      Registra /fichar, /pausar, /hoy y otros comandos en Telegram.

Tests:
  ./run_tests.sh
      Suite con unittest (stdlib). Todo en dry-run: no toca red ni Sesame.

Seguridad:
  ./secure_perms.sh
      Permisos 600 en config.json, links.json, audit.jsonl, dry_state.json.

  ./arm_real.sh        (y ./arm_real.sh off)
      Arma/desarma el 3er factor (ENABLE_REAL) para la prueba real controlada.
      No ficha por si solo: ver docs/security.md.

Telegram:
  /start       ayuda inicial
  /ayuda       ayuda completa
  /vincular    vincula el chat (codigo OTP por consola)
  /modo        modo de seguridad
  /sesion      comprueba sesion Sesame
  /estado      estado real o simulado
  /hoy         fichajes de hoy
  /fichar      entrar/salir
  /pausar      empezar/terminar descanso

Servicio siempre encendido:
  docs/always-on.md

Sesion Sesame:
  docs/sesame-session.md

Autorizacion Telegram:
  docs/telegram-auth.md

Modelo de seguridad (OTP, 3er factor, idempotencia):
  docs/security.md

Siri / Atajos iPhone:
  docs/siri-shortcuts.md

Parar si corre en terminal:
  Ctrl+C

Parar si corre como servicio:
  systemctl --user stop sesame-fichaje-bot.service
EOF
