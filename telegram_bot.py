"""
Bot de Telegram para fichar/pausar en Sesame (long-polling, sin dependencias).

- Habla con la Bot API por HTTP; no arranca sin BOT_TELEGRAM_TOKEN.
- Seguro por defecto: en dry-run NO ficha nada real (ver sesame_client). El modo
  real exige 3 factores (BOT_DRY_RUN=0 + BOT_ALLOW_REAL=1 + ENABLE_REAL) y chat
  vinculado por OTP.
- Emparejamiento chat<->empleado por OTP impreso en la CONSOLA del servidor
  (segundo factor fuera de banda), persistido en LinkStore (JSON, chmod 600). El
  OTP confirma ESTE chat; el employeeId vinculado sale de config (modelo de un solo
  usuario), no se verifica contra el teléfono de Sesame.
"""

import contextlib
import json
import logging
import os
import hashlib
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

try:
    import fcntl  # POSIX: lock de fichero entre procesos/reinicios
except ImportError:  # pragma: no cover  (no-POSIX)
    fcntl = None

import link_store
import sesame_client
import state_machine as sm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("telegram_bot")

BOT_VERSION = "1.0.5"

CONFIG = sesame_client.load_config()
TOKEN = os.environ.get("BOT_TELEGRAM_TOKEN") or CONFIG.get("telegram_token", "")
API = f"https://api.telegram.org/bot{TOKEN}"

LINKS_FILE = Path(os.environ.get("BOT_LINKS_FILE", CONFIG.get("links_file", "links.json")))
LINKS = link_store.LinkStore(LINKS_FILE)   # chat_id -> employeeId (persistente; binding por OTP)
PENDING = {}        # chat_id -> dict(command, plan, state, expires_at)
PENDING_OTP = {}    # chat_id -> dict(code, expires_at) para /vincular
FAKE_STATE = os.environ.get("BOT_FAKE_STATE", "out")  # estado simulado para dry-run
DRY_STATE = {}       # employeeId -> estado simulado mientras corre el proceso
LOCKS = set()       # employeeId en ejecución (lock en memoria; en real se añade flock)
RATE = {}           # chat_id -> [timestamps]

OTP_TTL_SECONDS = int(os.environ.get("BOT_OTP_TTL_SECONDS", "300"))
LOCK_DIR = Path(os.environ.get("BOT_LOCK_DIR", CONFIG.get("lock_dir", ".locks")))
CONFIRM_TTL_SECONDS = int(os.environ.get("BOT_CONFIRM_TTL_SECONDS", "120"))
RATE_LIMIT_COUNT = int(os.environ.get("BOT_RATE_LIMIT_COUNT", "30"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("BOT_RATE_LIMIT_WINDOW_SECONDS", "60"))
AUDIT_LOG = Path(os.environ.get("BOT_AUDIT_LOG", CONFIG.get("audit_log", "audit.jsonl")))
DRY_STATE_FILE = Path(os.environ.get("BOT_DRY_STATE_FILE", CONFIG.get("dry_state_file", "dry_state.json")))
OFFSET_FILE = Path(os.environ.get("BOT_OFFSET_FILE", CONFIG.get("offset_file", "tg_offset")))
REMINDERS_STATE_FILE = Path(os.environ.get("BOT_REMINDERS_STATE_FILE", CONFIG.get("reminders_state_file", "reminders_state.json")))
REMINDER_CONFIRM_TTL_SECONDS = int(os.environ.get("BOT_REMINDER_CONFIRM_TTL_SECONDS", "1800"))
_REMINDERS = {}   # tarea -> fecha (YYYY-MM-DD) en que se disparó por última vez

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

PUBLIC_COMMANDS = {"/start", "/ayuda", "/mi_chat_id"}


def _tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"{API}/{method}", data=data, timeout=35) as r:
        return json.load(r)


def send(chat_id, text, reply_markup=None):
    params = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        params["reply_markup"] = json.dumps(reply_markup)
    # Reintento ÚNICO ante errores de red transitorios: un mensaje de resultado
    # perdido es un fallo de fiabilidad (el usuario no ve la verdad y puede repetir
    # el comando). Solo afecta a sendMessage; el POST de fichaje NUNCA pasa por aquí.
    for attempt in (1, 2):
        try:
            _tg("sendMessage", **params)
            return
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            log.warning("sendMessage intento %d falló: %s", attempt, e)
            if attempt == 1:
                time.sleep(1)
        except Exception as e:  # noqa: BLE001
            log.error("sendMessage falló (no reintentable): %s", e)
            return


def _fingerprint(value) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def _secure_chmod(path):
    """Fuerza permisos 600 (solo el dueño) en ficheros con datos sensibles."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def audit(event: str, chat_id=None, employee_id=None, **fields) -> bool:
    """Registra un evento en el JSONL append-only. Devuelve True si se escribió.

    Nunca guarda secretos ni ids en claro (chat/employee van como sha256[:16]).
    """
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
        _secure_chmod(AUDIT_LOG)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("audit falló: %s", e)
        return False


@contextlib.contextmanager
def employee_lock(employee_id):
    """Lock por empleado. En memoria + flock entre procesos/reinicios (si hay POSIX).

    Evita acciones solapadas aunque haya dos instancias del bot o un reinicio.
    Lanza BusyEmployee si ya está bloqueado.
    """
    if employee_id in LOCKS:
        raise BusyEmployee(employee_id)
    LOCKS.add(employee_id)
    lock_file = None
    try:
        if fcntl is not None:
            LOCK_DIR.mkdir(parents=True, exist_ok=True)
            lock_file = (LOCK_DIR / f"{_fingerprint(employee_id)}.lock").open("w")
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise BusyEmployee(employee_id) from exc
        yield
    finally:
        if lock_file is not None:
            with contextlib.suppress(Exception):
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()
        LOCKS.discard(employee_id)


class BusyEmployee(Exception):
    """El empleado ya tiene una acción en curso (lock tomado)."""


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
    bound = "sí" if LINKS.get(chat_id) else "no"
    armed, reason = sesame_client.real_path_armed()
    armed_txt = "sí" if armed else f"no ({reason})"
    return (
        f"Modo actual: {mode_label()}.\n"
        f"- Chat autorizado: {allowed}\n"
        f"- Chat vinculado (OTP): {bound}\n"
        f"- Lee estado real de Sesame: {real_state}\n"
        f"- Ejecuta fichajes reales: {real_actions}\n"
        f"- Camino real armado (3er factor): {armed_txt}\n"
        f"- Kill switch: {'activo' if kill_switch_enabled() else 'apagado'}"
    )


def _git_sha():
    """Hash corto del commit desplegado (best-effort; vacío si no hay git)."""
    try:
        import subprocess
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, timeout=2,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def version_text():
    sha = _git_sha()
    return f"Versión: {BOT_VERSION}" + (f" ({sha})" if sha else "")


def enable_real_days_left():
    """Días que le quedan a la ventana ENABLE_REAL (None si no está armado)."""
    f = sesame_client.ENABLE_REAL_FILE
    if not f.exists():
        return None
    try:
        left = sesame_client.ENABLE_REAL_TTL - (time.time() - f.stat().st_mtime)
    except OSError:
        return None
    return left / 86400.0


def salud_text(chat_id):
    """Chequeo de salud: versión, modo, token vivo y ventana del 3er factor.
    Solo lecturas; nunca ficha."""
    lines = [version_text(), f"Modo: {mode_label()}"]
    lines.append(f"Chat vinculado (OTP): {'sí' if LINKS.get(chat_id) else 'no'}")
    if sesame_client.DRY_RUN:
        lines.append("Sesión Sesame: no aplica (simulación).")
    else:
        employee_id = resolve_employee_id(chat_id)
        if not employee_id:
            lines.append("Sesión Sesame: sin empleado vinculado (usa /vincular).")
        else:
            try:
                state = sesame_client.get_current_state(employee_id)
                lines.append(f"Sesión Sesame: OK · estado {state_label(state)}")
            except Exception:  # noqa: BLE001
                lines.append("Sesión Sesame: ⚠️ no conectada (¿token caducado? recaptúralo).")
    days = enable_real_days_left()
    if days is None:
        lines.append("ENABLE_REAL: no armado")
    else:
        lines.append(f"ENABLE_REAL: {'vigente' if days > 0 else 'caducado'} ({days:.1f} días)")
    lines.append(f"Kill switch: {'activo' if kill_switch_enabled() else 'apagado'}")
    return "\n".join(lines)


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
        "- /salud: versión, sesión de Sesame y ventana del 3er factor.\n"
        "- /version: versión del bot desplegada.\n"
        "- /mi_chat_id: muestra tu chat_id para autorizar este chat.\n"
        "- /reset: reinicia el estado simulado a fuera (solo pruebas).\n"
        "- /vincular: vincula este chat con tu usuario (codigo OTP por consola).\n"
        "- /desvincular: desvincula este chat de tu usuario.\n"
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


def run_plan(chat_id, employee_id, plan, command=None, expected_state=None, recheck=True):
    if kill_switch_enabled():
        audit("blocked_kill_switch", chat_id, employee_id, actions=plan.actions)
        return send(chat_id, "Acciones bloqueadas por kill switch.")

    # Re-lectura de idempotencia: relevante cuando hubo un hueco de interacción
    # (confirmación SI/NO). En la ruta inmediata el estado se acaba de leer, así que
    # se omite (recheck=False) para no hacer dos round-trips a Sesame.
    if recheck and command and expected_state is not None:
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

    real = not sesame_client.DRY_RUN and sesame_client.ALLOW_REAL
    # En real, si no podemos dejar traza del intento, NO ejecutamos (un fichaje sin
    # auditar es peor que no fichar).
    started = audit("execute_plan_start", chat_id, employee_id, actions=plan.actions, dry_run=sesame_client.DRY_RUN)
    if real and not started:
        return send(chat_id, "No puedo registrar la auditoría; no ejecuto el fichaje real.")

    try:
        with employee_lock(employee_id):
            results = sesame_client.execute_plan(plan.actions, employee_id)
    except BusyEmployee:
        audit("blocked_lock", chat_id, employee_id, actions=plan.actions)
        return send(chat_id, "Ya hay una acción en curso para este empleado. Prueba de nuevo en unos segundos.")
    except Exception as e:  # noqa: BLE001
        audit("execute_plan_error", chat_id, employee_id, actions=plan.actions, error=str(e)[:200])
        return send(chat_id, f"No se pudo completar: {e}", remove_keyboard())

    if results and results[0].get("dry_run"):
        new_state = apply_dry_run_state(employee_id, plan.actions)
        audit("execute_plan_dry_run", chat_id, employee_id, actions=plan.actions)
        return send(
            chat_id,
            "🧪 (simulación) "
            + plan.description
            + "\n"
            + actions_label(plan.actions)
            + f"\nEstado simulado: {state_label(new_state)}",
            remove_keyboard(),
        )

    # Camino real: solo "✅" si TODAS las acciones fueron 2xx (#5). Si alguna falló,
    # avisamos del plan a medias releyendo el estado real (#2) en vez de mentir.
    statuses = [r.get("status") for r in results]
    done = [r["action"] for r in results if r.get("ok")]
    failed = next((r for r in results if not r.get("ok")), None)

    if results and failed is None:
        audit("execute_plan_ok", chat_id, employee_id, actions=plan.actions, statuses=statuses)
        # Recibo read-after-write: confirmamos releyendo el estado real de Sesame, en
        # vez de fiarnos de un "✅" a ciegas. El usuario ve la verdad de lo que quedó.
        try:
            receipt = f"✅ {plan.description}.\nAhora: {state_label(get_state(employee_id))}."
        except Exception:  # noqa: BLE001
            receipt = f"✅ {plan.description}.\n(No pude confirmar el estado; revisa con /estado.)"
        return send(chat_id, receipt, remove_keyboard())

    err = str((failed or {}).get("error", ""))
    audit(
        "execute_plan_partial", chat_id, employee_id,
        actions=plan.actions, done=done,
        failed=(failed or {}).get("action"), statuses=statuses,
        error=err[:200],
    )
    # Token/sesión caducada: fallar EN VOZ ALTA. El peor caso es creer que has fichado
    # y no haberlo hecho.
    if "401" in err or "403" in err:
        return send(
            chat_id,
            "⚠️ Tu sesión de Sesame ha caducado: el fichaje NO se registró.\n"
            "Recaptura el token (usid/csid/esid) en config.json y reinicia el bot.",
            remove_keyboard(),
        )
    try:
        state_txt = f"\nEstado actual en Sesame: {state_label(get_state(employee_id))}."
    except Exception:  # noqa: BLE001
        state_txt = ""
    failed_label = ACTION_LABELS.get((failed or {}).get("action"), (failed or {}).get("action", "?"))
    if done:
        head = f"⚠️ Acción a medias: se hizo «{actions_label(done)}» pero falló «{failed_label}»."
    else:
        head = f"❌ No se pudo ejecutar «{failed_label}»."
    return send(chat_id, head + state_txt + "\nRevisa y reintenta.", remove_keyboard())


def resolve_employee_id(chat_id):
    """Resuelve el employeeId del chat.

    Gate R1: en modo REAL el employeeId se lee SOLO del binding (LinkStore), nunca
    del mensaje. Matiz honesto (modelo de un solo usuario): ese binding se rellenó
    desde config.employee_id al verificar el OTP, así que el OTP confirma "este
    chat", no la identidad en Sesame. En dry-run/desarrollo se admite el fallback a
    BOT_TEST_EMPLOYEE_ID / config para poder probar sin vincular.
    """
    bound = LINKS.get(chat_id)
    if not sesame_client.DRY_RUN and sesame_client.ALLOW_REAL:
        return bound
    return bound or os.environ.get("BOT_TEST_EMPLOYEE_ID") or CONFIG.get("employee_id")


def cmd_vincular(chat_id):
    """Inicia el emparejamiento: genera un OTP que SOLO se imprime en la consola del
    servidor (segundo factor fuera de banda) y queda pendiente de confirmación."""
    employee_id = CONFIG.get("employee_id")
    if not employee_id:
        return send(chat_id, "No hay employee_id en config.json para vincular.")
    code = f"{secrets.randbelow(1000000):06d}"
    PENDING_OTP[chat_id] = {"code": code, "expires_at": time.time() + OTP_TTL_SECONDS}
    # A la CONSOLA/journald (solo lo ve quien opera el servidor), no a Telegram.
    log.warning("[VINCULACION] Código para el chat %s: %s (caduca en %ss)",
                chat_id, code, OTP_TTL_SECONDS)
    audit("otp_issued", chat_id)
    return send(
        chat_id,
        "He impreso un código de vinculación en la consola del servidor (solo tú la "
        "ves). Escríbelo aquí para vincular este chat con tu usuario de Sesame.",
    )


def cmd_otp_code(chat_id, code):
    """Verifica el OTP y, si es correcto, persiste el binding chat -> employeeId."""
    otp = PENDING_OTP.pop(chat_id, None)
    if not otp:
        return send(chat_id, "No hay vinculación en curso. Usa /vincular.")
    if time.time() > otp["expires_at"]:
        audit("otp_expired", chat_id)
        return send(chat_id, "El código ha caducado. Usa /vincular otra vez.")
    if not secrets.compare_digest(code, otp["code"]):
        audit("otp_mismatch", chat_id)
        return send(chat_id, "Código incorrecto. Usa /vincular para generar uno nuevo.")
    employee_id = CONFIG.get("employee_id")
    LINKS.set(chat_id, employee_id)
    audit("otp_bound", chat_id, employee_id)
    return send(chat_id, "✅ Vinculado. Este chat ya puede fichar en tu usuario de Sesame.")


def handle(chat_id, text):
    t = (text or "").strip().lower()

    if t == "/start":
        return send(chat_id, start_text())
    if t == "/ayuda":
        return send(chat_id, help_text())
    if t == "/mi_chat_id":
        return send(chat_id, f"Tu chat_id es: {chat_id}\nAñádelo a authorized_chat_ids en config.json.")

    if t not in PUBLIC_COMMANDS and not is_authorized(chat_id):
        audit("blocked_unauthorized_chat", chat_id)
        return send(chat_id, "Chat no autorizado. Usa /mi_chat_id y añade ese id a config.json.")

    # Diagnóstico (solo lectura): no requieren binding, útiles cuando algo va mal.
    if t == "/version":
        return send(chat_id, version_text())
    if t == "/salud":
        return send(chat_id, salud_text(chat_id))

    # Vinculación por OTP: no requiere binding previo (lo crea). Rate-limit para
    # evitar fuerza bruta del código.
    if t == "/vincular" or (chat_id in PENDING_OTP and t.isdigit()):
        if rate_limited(chat_id):
            audit("blocked_rate_limit", chat_id)
            return send(chat_id, "Demasiadas peticiones seguidas. Espera un momento.")
        if t == "/vincular":
            return cmd_vincular(chat_id)
        return cmd_otp_code(chat_id, t)

    employee_id = resolve_employee_id(chat_id)
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
    if t == "/desvincular":
        if LINKS.get(chat_id):
            LINKS.remove(chat_id)
            audit("unbound", chat_id, employee_id)
            return send(chat_id, "Desvinculado. Este chat ya no está asociado a tu usuario. Usa /vincular para volver a vincular.")
        return send(chat_id, "Este chat no estaba vinculado.")

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
        # Ruta inmediata: el estado se acaba de leer; no hace falta re-leerlo (#6).
        return run_plan(chat_id, employee_id, plan, command=command, expected_state=state, recheck=False)

    send(chat_id, "No te he entendido. Usa: /fichar · /pausar · /estado")


# --- Recordatorios programados (scheduler integrado en el loop; sin hilos) -------------
# Dos tareas, una vez al día: (1) probe de solo lectura del token y aviso si caduca;
# (2) recordatorio "sigues fichado" a tu hora de salida, con botón SI para fichar salida
# (pasa por el flujo normal con re-lectura y guardas; NUNCA ficha solo).

def reminders_config():
    return CONFIG.get("reminders") or {}


def _parse_hhmm(value):
    try:
        hh, mm = str(value).strip().split(":")
        hh, mm = int(hh), int(mm)
        if 0 <= hh < 24 and 0 <= mm < 60:
            return hh, mm
    except (ValueError, AttributeError):
        pass
    return None


def load_reminders_state():
    global _REMINDERS
    if not REMINDERS_STATE_FILE.exists():
        return
    try:
        data = json.loads(REMINDERS_STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            _REMINDERS = {str(k): str(v) for k, v in data.items()}
    except Exception as e:  # noqa: BLE001
        log.error("No se pudo cargar reminders_state: %s", e)


def save_reminders_state():
    try:
        REMINDERS_STATE_FILE.write_text(json.dumps(_REMINDERS, indent=2), encoding="utf-8")
        _secure_chmod(REMINDERS_STATE_FILE)
    except Exception as e:  # noqa: BLE001
        log.error("No se pudo guardar reminders_state: %s", e)


def _reminder_due(now, sched_hhmm, last_date, window_min=None) -> bool:
    """True si la tarea aún no se disparó hoy y la hora actual ya pasó la programada
    (y, si se indica window_min, no se ha pasado de la ventana — para no disparar tarde
    tras un arranque a deshora)."""
    if sched_hhmm is None:
        return False
    if last_date == now.date().isoformat():
        return False
    sched = now.replace(hour=sched_hhmm[0], minute=sched_hhmm[1], second=0, microsecond=0)
    if now < sched:
        return False
    if window_min is not None and now > sched + timedelta(minutes=window_min):
        return False
    return True


def _bound_chats():
    for chat_str, employee_id in LINKS.all().items():
        try:
            yield int(chat_str), employee_id
        except ValueError:
            yield chat_str, employee_id


def _run_token_probe(cfg):
    """Solo lectura: comprueba que la sesión de Sesame responde; avisa si no, y si
    ENABLE_REAL está a punto de caducar."""
    if sesame_client.DRY_RUN:
        return
    warn_days = float(cfg.get("enable_real_warn_days", 3))
    days = enable_real_days_left()
    for chat_id, employee_id in _bound_chats():
        try:
            sesame_client.get_current_state(employee_id)
        except Exception:  # noqa: BLE001
            audit("reminder_token_dead", chat_id, employee_id)
            send(chat_id, "⚠️ No puedo conectar con Sesame: tu sesión pudo caducar. "
                          "Recaptura usid/csid/esid en config.json y reinicia el bot.")
        if days is not None and days <= warn_days:
            audit("reminder_enable_real_soon", chat_id)
            send(chat_id, f"🔐 ENABLE_REAL caduca en {days:.1f} días. "
                          "Re-arma con ./arm_real.sh en el servidor.")


def _run_clock_out_reminder(cfg):
    """Si sigues fichado a tu hora de salida, te avisa con botón SI para fichar salida
    (deja un PENDING; el SI pasa por run_plan con re-lectura, igual que un fichar normal)."""
    label = cfg.get("clock_out_time", "")
    for chat_id, employee_id in _bound_chats():
        try:
            state = get_state(employee_id)
        except Exception:  # noqa: BLE001
            continue
        if state not in (sm.WORKING, sm.REMOTE):
            continue
        plan = sm.plan_actions(state, sm.FICHAR)   # trabajando -> CLOCK_OUT (con confirmación)
        if not plan.actions:
            continue
        PENDING[chat_id] = {
            "command": sm.FICHAR, "plan": plan, "state": state,
            "expires_at": time.time() + REMINDER_CONFIRM_TTL_SECONDS,
        }
        audit("reminder_clock_out", chat_id, employee_id, state=state)
        send(chat_id,
             f"⏰ Son las {label} (tu hora de salida) y sigues {state_label(state)}. "
             "¿Cierro la jornada antes de que Sesame marque incidencia?\n"
             "Pulsa SI para fichar salida o NO para seguir.",
             confirm_keyboard())


def run_scheduled(now=None):
    """Comprueba y dispara las tareas programadas (llamado en cada vuelta del loop)."""
    cfg = reminders_config()
    if not cfg.get("enabled"):
        return
    now = now or datetime.now()
    today = now.date().isoformat()

    if _reminder_due(now, _parse_hhmm(cfg.get("token_probe_time", "08:00")), _REMINDERS.get("token_probe")):
        try:
            _run_token_probe(cfg)
        finally:
            _REMINDERS["token_probe"] = today
            save_reminders_state()

    window = int(cfg.get("clock_out_window_min", 120))
    if _reminder_due(now, _parse_hhmm(cfg.get("clock_out_time")), _REMINDERS.get("clock_out"), window_min=window):
        try:
            _run_clock_out_reminder(cfg)
        finally:
            _REMINDERS["clock_out"] = today
            save_reminders_state()


def load_offset() -> int:
    try:
        return int(OFFSET_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0


def save_offset(offset):
    with contextlib.suppress(OSError):
        OFFSET_FILE.write_text(str(offset), encoding="utf-8")


def main():
    if not TOKEN or TOKEN == "PEGA_AQUI_EL_TOKEN_DE_BOTFATHER":
        raise SystemExit("Configura BOT_TELEGRAM_TOKEN (de @BotFather) para arrancar.")
    load_dry_state()
    load_reminders_state()
    log.info("Bot arrancado. DRY_RUN=%s ALLOW_REAL=%s", sesame_client.DRY_RUN, sesame_client.ALLOW_REAL)
    offset = load_offset()
    backoff = 1
    while True:
        try:
            upd = _tg("getUpdates", offset=offset, timeout=30)
            backoff = 1  # éxito: reinicia el backoff
            for u in upd.get("result", []):
                offset = u["update_id"] + 1
                # Marcamos el update como procesado ANTES de actuar: ante un crash se
                # pierde el mensaje (reintentable) en vez de duplicar un fichaje.
                save_offset(offset)
                msg = u.get("message") or {}
                chat = (msg.get("chat") or {}).get("id")
                if chat is None:
                    continue
                # Un mensaje problemático no debe tumbar el loop ni disparar backoff de red.
                try:
                    handle(chat, msg.get("text", ""))
                except Exception as e:  # noqa: BLE001
                    log.error("handle(%s): %s", chat, e)
            # Tareas programadas (probe del token, recordatorio de salida). Aisladas:
            # un fallo aquí no debe tumbar el loop ni disparar el backoff de red.
            try:
                run_scheduled()
            except Exception as e:  # noqa: BLE001
                log.error("run_scheduled: %s", e)
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
