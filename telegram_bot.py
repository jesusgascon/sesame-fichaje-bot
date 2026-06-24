"""
Esqueleto del bot de Telegram para fichar/pausar (DRY-RUN).

- Sin dependencias externas: habla con la Bot API por HTTP (long-polling).
- No arranca si no hay BOT_TELEGRAM_TOKEN (evita ejecuciones accidentales).
- En dry-run NO ficha nada real (ver sesame_client).
- Emparejamiento chat<->empleado: STUB en memoria. Fase 2: contacto + OTP
  verificado contra el teléfono de tu perfil de Sesame, y almacén cifrado.
"""

import json
import logging
import os
import time
import urllib.parse
import urllib.request

import sesame_client
import state_machine as sm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("telegram_bot")

TOKEN = os.environ.get("BOT_TELEGRAM_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"

LINKS = {}          # chat_id -> employeeId (Fase 2: OTP + cifrado)
PENDING = {}        # chat_id -> (command, plan)
FAKE_STATE = os.environ.get("BOT_FAKE_STATE", "out")  # estado simulado para dry-run


def _tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"{API}/{method}", data=data, timeout=35) as r:
        return json.load(r)


def send(chat_id, text):
    try:
        _tg("sendMessage", chat_id=chat_id, text=text)
    except Exception as e:  # noqa: BLE001
        log.error("sendMessage falló: %s", e)


def get_state(employee_id):
    """Estado actual del empleado. STUB en dry-run; Fase 2: leer de Sesame."""
    return FAKE_STATE


def run_plan(chat_id, employee_id, plan):
    results = sesame_client.execute_plan(plan.actions, employee_id)
    if results and results[0].get("dry_run"):
        send(chat_id, "🧪 (simulación) " + plan.description + "\n" + " → ".join(plan.actions))
    else:
        send(chat_id, "✅ " + plan.description)


def handle(chat_id, text):
    t = (text or "").strip().lower()

    if t in ("/start", "/ayuda"):
        return send(chat_id, "Bot de fichaje (en pruebas).\nComandos: fichar · pausar · /estado · /vincular")
    if t == "/vincular":
        return send(chat_id, "Vinculación pendiente (Fase 2: contacto + OTP).")

    employee_id = LINKS.get(chat_id) or os.environ.get("BOT_TEST_EMPLOYEE_ID")
    if not employee_id:
        return send(chat_id, "No estás vinculado. Usa /vincular.")

    if t == "/estado":
        return send(chat_id, f"Estado actual: {get_state(employee_id)}")

    if chat_id in PENDING and t in ("si", "sí", "confirmar"):
        _, plan = PENDING.pop(chat_id)
        return run_plan(chat_id, employee_id, plan)
    if chat_id in PENDING and t in ("no", "cancelar"):
        PENDING.pop(chat_id)
        return send(chat_id, "Cancelado.")

    if t in (sm.FICHAR, "/fichar", sm.PAUSAR, "/pausar"):
        command = sm.FICHAR if "fich" in t else sm.PAUSAR
        state = get_state(employee_id)
        plan = sm.plan_actions(state, command)
        if not plan.actions:
            return send(chat_id, "No sé qué hacer en tu estado actual.")
        if plan.needs_confirmation:
            PENDING[chat_id] = (command, plan)
            return send(chat_id, f"Estás *{state}*. {plan.description}.\nResponde SI para confirmar o NO para cancelar.")
        return run_plan(chat_id, employee_id, plan)

    send(chat_id, "No te he entendido. Usa: fichar · pausar · /estado")


def main():
    if not TOKEN:
        raise SystemExit("Configura BOT_TELEGRAM_TOKEN (de @BotFather) para arrancar.")
    log.info("Bot arrancado. DRY_RUN=%s ALLOW_REAL=%s", sesame_client.DRY_RUN, sesame_client.ALLOW_REAL)
    offset = 0
    while True:
        try:
            upd = _tg("getUpdates", offset=offset, timeout=30)
            for u in upd.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                chat = (msg.get("chat") or {}).get("id")
                if chat is not None:
                    handle(chat, msg.get("text", ""))
        except Exception as e:  # noqa: BLE001
            log.error("loop: %s", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
