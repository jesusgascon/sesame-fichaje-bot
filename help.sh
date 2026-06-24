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

  python3 probe_sesame_state.py
      Lee el estado real actual de Sesame.

  python3 probe_sesame_readonly.py
      Comprueba sesion y tipos asignados.

  python3 probe_pause_candidates.py
      Busca el id de Descanso en checks existentes.

  python3 set_telegram_commands.py
      Registra /fichar, /pausar, /hoy y otros comandos en Telegram.

Telegram:
  /start       ayuda inicial
  /ayuda       ayuda completa
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

Siri / Atajos iPhone:
  docs/siri-shortcuts.md

Parar si corre en terminal:
  Ctrl+C

Parar si corre como servicio:
  systemctl --user stop sesame-fichaje-bot.service
EOF
