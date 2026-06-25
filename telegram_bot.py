"""
Esqueleto del bot de Telegram para fichar/pausar (DRY-RUN).

- Sin dependencias externas: habla con la Bot API por HTTP (long-polling).
- No arranca si no hay BOT_TELEGRAM_TOKEN (evita ejecuciones accidentales).
- En dry-run NO ficha nada real (ver sesame_client).
- Emparejamiento chat<->empleado: persistido en LinkStore (JSON). Fase 2: contacto
  + OTP verificado contra el teléfono de tu perfil de Sesame, y almacén cifrado.
"""

import json
import logging
import os
import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import link_store
import sesame_client
import state_machine as sm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("telegram_bot")

CONFIG = sesame_client.load_config()
TOKEN = os.environ.get("BOT_TELEGRAM_TOKEN") or CONFIG.get("telegram_token", "")
API = f"https://api.telegram.org/bot{TOKEN}"

LINKS_FILE = Path(os.environ.get("BOT_LINKS_FILE", CONFIG.get("links_file", "links.json")))
LINKS = link_store.LinkStore(LINKS_FILE)   # chat_id -> employeeId (persistente; Fase 2: OTP + cifrado)
PENDING = {}        # chat_id -> dict(command, plan, state, expires_at)
FAKE_STATE = os.environ.get("BOT_FAKE_STATE", "out")  # estado simulado para dry-run
DRY_STATE = {}       # employeeId -> estado simulado mientras corre el proceso
LOCKS = set()       # employeeId en ejecución
RATE = {}           # chat_id -> [timestamps]

CONFIRM_TTL_SECONDS = int(os.environ.get("BOT_CONFIRM_TTL_SECONDS", "120"))
RATE_LIMIT_COUNT = int(os.environ.get("BOT_RATE_LIMIT_COUNT", "30"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("BOT_RATE_LIMIT_WINDOW_SECONDS", "60"))
AUDIT_LOG = Path(os.environ.get("BOT_AUDIT_LOG", CONFIG.get("audit_log", "audit.jsonl")))
DRY_STATE_FILE = Path(os.environ.get("BOT_DRY_STATE_FILE", CONFIG.get("dry_state_file", "dry_state.json")))

STATE_LABELS = {
    sm.OUT: "fuera",
    sm.WORKING: "trabajando",
    sm.PAUSED: "descansando",
    sm.REMOTE: "teletrabajando",
}

ACTION_LABELS = {
    sm.CLOCK_IN: "entrar",
    sm.CLOCK_OUT: "salir",
    sm.PAUSE_START: "empezar descanso",
    sm.PAUSE_END: "terminar descanso",
}

PUBLIC_COMMANDS = {"/start", "/ayuda", "/vincular", "/mi_chat_id"}


def _tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"{API}/{method}", data=data, timeout=35) as r:
        return json.load(r)


def send(chat_id, text, reply_markup=None):
    params = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        params["reply_markup"] = json.dumps(reply_markup)
    try:
        _tg("sendMessage", **params)
    except Exception as e:  # noqa: BLE001
        log.error("sendMessage falló: %s", e)


def _fingerprint(value) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def audit(event: str, chat_id=None, employee_id=None, **fields):
    record = {
        "ts": int(time.time()),
        "event": event,
        "chat": _fingerprint(chat_id) if chat_id is not None else None,
        "employee": _fingerprint(employee_id) if employee_id is not None else None,
        **fields,
    }
    try:
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        log.error("audit falló: %s", e)


def kill_switch_enabled() -> bool:
    env = os.environ.get("BOT_KILL_SWITCH")
    if env is not None:
        return env == "1"
    # Releído en caliente desde disco: poner "kill_switch": true en config.json
    # surte efecto sin reiniciar el bot (importante en una emergencia).
    try:
        return bool(sesame_client.load_config().get("kill_switch", False))
    except Exception:  # noqa: BLE001
        return bool(CONFIG.get("kill_switch", False))


def rate_limited(chat_id) -> bool:
    now = time.time()
    recent = [
        t for t in RATE.get(chat_id, [])
        if now - t < RATE_LIMIT_WINDOW_SECONDS
    ]
    # Si ya se alcanzó el límite, NO contamos este intento: así una ráfaga de
    # mensajes bloqueados no renueva indefinidamente la ventana.
    if len(recent) >= RATE_LIMIT_COUNT:
        RATE[chat_id] = recent
        return True
    recent.append(now)
    RATE[chat_id] = recent
    return False


def confirm_keyboard():
    return {
        "keyboard": [["SI", "NO"]],
        "one_time_keyboard": True,
        "resize_keyboard": True,
    }


def remove_keyboard():
    return {"remove_keyboard": True}


def state_label(state):
    return STATE_LABELS.get(state, state)


def actions_label(actions):
    return " → ".join(ACTION_LABELS.get(action, action) for action in actions)


def authorized_chat_ids():
    return {str(chat_id) for chat_id in CONFIG.get("authorized_chat_ids", [])}


def is_authorized(chat_id):
    allowed = authorized_chat_ids()
    return bool(allowed) and str(chat_id) in allowed


def start_text():
    mode = mode_label()
    return (
        "Hola. Soy tu bot de fichaje de Sesame.\n\n"
        f"Modo actual: {mode}.\n"
        "Ahora mismo las acciones no fichan real salvo que el modo real esté habilitado.\n\n"
        "Comandos principales:\n"
        "- /estado: ver si estás fuera, trabajando o descansando.\n"
        "- /hoy: ver tus fichajes de hoy.\n"
        "- /fichar: entrar o salir.\n"
        "- /pausar: empezar o terminar descanso.\n"
        "- /sesion: comprobar conexión con Sesame.\n"
        "- /modo: ver modo de seguridad actual.\n"
        "- /mi_chat_id: ver tu identificador de chat para autorizarte.\n"
        "- /ayuda: ver ayuda completa."
    )


def mode_label():
    if sesame_client.DRY_RUN:
        return "simulación pura"
    if not sesame_client.ALLOW_REAL:
        return "estado real + acciones simuladas"
    return "real"


def mode_text(chat_id):
    allowed = "sí" if is_authorized(chat_id) else "no"
    real_state = "sí" if not sesame_client.DRY_RUN else "no"
    real_actions = "sí" if sesame_client.ALLOW_REAL else "no"
    return (
        f"Modo actual: {mode_label()}.\n"
        f"- Chat autorizado: {allowed}\n"
        f"- Lee estado real de Sesame: {real_state}\n"
        f"- Ejecuta fichajes reales: {real_actions}\n"
        f"- Kill switch: {'activo' if kill_switch_enabled() else 'apagado'}"
    )


def help_text():
    mode = mode_label()
    return (
        f"Bot de fichaje Sesame ({mode}).\n\n"
        "Comandos:\n"
        "- /fichar o fichar: inicia o finaliza la jornada.\n"
        "- /pausar o pausar: inicia o termina una pausa.\n"
        "- /estado: muestra el estado actual.\n"
        "- /hoy: muestra los fichajes de hoy.\n"
        "- /sesion: comprueba si la sesion de Sesame sigue viva.\n"
        "- /modo: muestra modo actual y guardas activas.\n"
        "- /mi_chat_id: muestra tu chat_id para autorizar este chat.\n"
        "- /reset: reinicia el estado simulado a fuera (solo pruebas).\n"
        "- /vincular: pendiente; enlazara tu Telegram con tu empleado.\n"
        "- /ayuda: muestra esta ayuda.\n\n"
        "Estados:\n"
        "- fuera: sin jornada abierta.\n"
        "- trabajando: jornada abierta.\n"
        "- descansando: pausa abierta.\n"
        "- teletrabajando: jornada remota abierta.\n\n"
        "Confirmaciones:\n"
        "- Finalizar jornada pide SI/NO.\n"
        "- Fichar estando en pausa cerrara pausa + jornada y pide SI/NO.\n"
        "- Pausar estando fuera pide SI/NO.\n\n"
        "Ahora mismo no ficha nada real salvo que el modo real este habilitado explicitamente."
    )


def load_dry_state():
    if not DRY_STATE_FILE.exists():
        return
    try:
        data = json.loads(DRY_STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            DRY_STATE.update({str(k): str(v) for k, v in data.items()})
    except Exception as e:  # noqa: BLE001
        log.error("No se pudo cargar estado dry-run: %s", e)


def save_dry_state():
    try:
        DRY_STATE_FILE.write_text(json.dumps(DRY_STATE, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log.error("No se pudo guardar estado dry-run: %s", e)


def reset_dry_state(employee_id):
    DRY_STATE[employee_id] = sm.OUT
    save_dry_state()


def sesame_session_status(employee_id):
    if sesame_client.DRY_RUN:
        return "Sesión Sesame: no comprobada en simulación pura."
    try:
        state = get_state(employee_id)
    except Exception as e:  # noqa: BLE001
        log.error("sesion Sesame falló: %s", e)
        return (
            "Sesión Sesame: no conectada.\n"
            "Actualiza usid/csid/esid en config.json y reinicia el bot."
        )
    return f"Sesión Sesame: conectada.\nEstado real: {state_label(state)}"


def get_state(employee_id):
    """Estado actual del empleado. En dry-run usa BOT_FAKE_STATE; si no, lee Sesame."""
    if sesame_client.DRY_RUN:
        return DRY_STATE.get(employee_id, FAKE_STATE)
    return sesame_client.get_current_state(employee_id)


def apply_dry_run_state(employee_id, actions):
    state = get_state(employee_id)
    for action in actions:
        if action == sm.CLOCK_IN:
            state = sm.WORKING
        elif action == sm.CLOCK_OUT:
            state = sm.OUT
        elif action == sm.PAUSE_START:
            state = sm.PAUSED
        elif action == sm.PAUSE_END:
            state = sm.WORKING
    DRY_STATE[employee_id] = state
    save_dry_state()
    return state


def run_plan(chat_id, employee_id, plan, command=None, expected_state=None):
    if kill_switch_enabled():
        audit("blocked_kill_switch", chat_id, employee_id, actions=plan.actions)
        return send(chat_id, "Acciones bloqueadas por kill switch.")

    if employee_id in LOCKS:
        audit("blocked_lock", chat_id, employee_id, actions=plan.actions)
        return send(chat_id, "Ya hay una acción en curso para este empleado. Prueba de nuevo en unos segundos.")

    if command and expected_state is not None:
        fresh_state = get_state(employee_id)
        fresh_plan = sm.plan_actions(fresh_state, command)
        if fresh_plan.actions != plan.actions:
            audit(
                "blocked_state_changed",
                chat_id,
                employee_id,
                expected_state=expected_state,
                fresh_state=fresh_state,
                original_actions=plan.actions,
                fresh_actions=fresh_plan.actions,
            )
            return send(chat_id, f"El estado cambió a {state_label(fresh_state)}. No ejecuto una acción antigua.")

    LOCKS.add(employee_id)
    audit("execute_plan_start", chat_id, employee_id, actions=plan.actions, dry_run=sesame_client.DRY_RUN)
    try:
        results = sesame_client.execute_plan(plan.actions, employee_id)
    finally:
        LOCKS.discard(employee_id)

    if results and results[0].get("dry_run"):
        new_state = apply_dry_run_state(employee_id, plan.actions)
        audit("execute_plan_dry_run", chat_id, employee_id, actions=plan.actions)
        send(
            chat_id,
            "🧪 (simulación) "
            + plan.description
            + "\n"
            + actions_label(plan.actions)
            + f"\nEstado simulado: {state_label(new_state)}",
            remove_keyboard(),
        )
    else:
        audit("execute_plan_ok", chat_id, employee_id, actions=plan.actions)
        send(chat_id, "✅ " + plan.description, remove_keyboard())


def handle(chat_id, text):
    t = (text or "").strip().lower()

    if t == "/start":
        return send(chat_id, start_text())
    if t == "/ayuda":
        return send(chat_id, help_text())
    if t == "/mi_chat_id":
        return send(chat_id, f"Tu chat_id es: {chat_id}\nAñádelo a authorized_chat_ids en config.json.")
    if t == "/vincular":
        return send(chat_id, "Vinculación pendiente. De momento usa /mi_chat_id y authorized_chat_ids en config.json.")

    if t not in PUBLIC_COMMANDS and not is_authorized(chat_id):
        audit("blocked_unauthorized_chat", chat_id)
        return send(chat_id, "Chat no autorizado. Usa /mi_chat_id y añade ese id a config.json.")

    employee_id = (
        LINKS.get(chat_id)
        or os.environ.get("BOT_TEST_EMPLOYEE_ID")
        or CONFIG.get("employee_id")
    )
    if not employee_id:
        return send(chat_id, "No estás vinculado. Usa /vincular.")

    if t == "/estado":
        return send(chat_id, f"Estado actual: {state_label(get_state(employee_id))}")
    if t == "/hoy":
        if sesame_client.DRY_RUN:
            return send(chat_id, "Fichajes de hoy no disponibles en simulación pura. Usa el modo de estado real.")
        lines = sesame_client.summarize_checks_today(employee_id)
        return send(chat_id, "Fichajes de hoy:\n" + "\n".join(lines))
    if t == "/sesion":
        return send(chat_id, sesame_session_status(employee_id))
    if t == "/modo":
        return send(chat_id, mode_text(chat_id))
    if t == "/reset":
        if sesame_client.DRY_RUN:
            reset_dry_state(employee_id)
            audit("dry_state_reset", chat_id, employee_id)
            return send(chat_id, "Simulación reiniciada. Estado actual: fuera")
        return send(chat_id, "Reset solo disponible en simulación.")

    if t in ("si", "sí", "confirmar", "no", "cancelar", sm.FICHAR, "/fichar", sm.PAUSAR, "/pausar"):
        if rate_limited(chat_id):
            audit("blocked_rate_limit", chat_id)
            return send(chat_id, "Demasiadas peticiones seguidas. Espera un momento.")

    if chat_id in PENDING and t in ("si", "sí", "confirmar"):
        pending = PENDING.pop(chat_id)
        if time.time() > pending["expires_at"]:
            audit("confirm_expired", chat_id, employee_id, command=pending["command"])
            return send(chat_id, "La confirmación ha caducado. Repite el comando.", remove_keyboard())
        audit("confirm_accept", chat_id, employee_id, command=pending["command"])
        return run_plan(
            chat_id,
            employee_id,
            pending["plan"],
            command=pending["command"],
            expected_state=pending["state"],
        )
    if chat_id in PENDING and t in ("no", "cancelar"):
        pending = PENDING.pop(chat_id)
        audit("confirm_cancel", chat_id, employee_id, command=pending["command"])
        return send(chat_id, "Cancelado.", remove_keyboard())

    if t in (sm.FICHAR, "/fichar", sm.PAUSAR, "/pausar"):
        command = sm.FICHAR if "fich" in t else sm.PAUSAR
        state = get_state(employee_id)
        plan = sm.plan_actions(state, command)
        if not plan.actions:
            return send(chat_id, "No sé qué hacer en tu estado actual.")
        if plan.needs_confirmation:
            PENDING[chat_id] = {
                "command": command,
                "plan": plan,
                "state": state,
                "expires_at": time.time() + CONFIRM_TTL_SECONDS,
            }
            audit("confirm_required", chat_id, employee_id, command=command, state=state, actions=plan.actions)
            return send(chat_id, f"Estás {state_label(state)}. {plan.description}.\nPulsa SI para confirmar o NO para cancelar.", confirm_keyboard())
        return run_plan(chat_id, employee_id, plan, command=command, expected_state=state)

    send(chat_id, "No te he entendido. Usa: /fichar · /pausar · /estado")


def main():
    if not TOKEN or TOKEN == "PEGA_AQUI_EL_TOKEN_DE_BOTFATHER":
        raise SystemExit("Configura BOT_TELEGRAM_TOKEN (de @BotFather) para arrancar.")
    load_dry_state()
    log.info("Bot arrancado. DRY_RUN=%s ALLOW_REAL=%s", sesame_client.DRY_RUN, sesame_client.ALLOW_REAL)
    offset = 0
    backoff = 1
    while True:
        try:
            upd = _tg("getUpdates", offset=offset, timeout=30)
            backoff = 1  # éxito: reinicia el backoff
            for u in upd.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                chat = (msg.get("chat") or {}).get("id")
                if chat is None:
                    continue
                # Un mensaje problemático no debe tumbar el loop ni disparar backoff de red.
                try:
                    handle(chat, msg.get("text", ""))
                except Exception as e:  # noqa: BLE001
                    log.error("handle(%s): %s", chat, e)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            # Errores de red esperables en long-polling: backoff exponencial con techo.
            log.warning("red: %s (reintento en %ss)", e, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception as e:  # noqa: BLE001
            log.error("loop: %s", e)
            time.sleep(min(backoff, 5))
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    main()
