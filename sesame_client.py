"""
Cliente de fichaje sobre Sesame (autónomo, con TU propio token).

SEGURIDAD POR DEFECTO: arranca en DRY-RUN. En dry-run NO se hace ninguna
petición a Sesame: solo se registra (log) "lo que se haría". El camino real exige
TRES factores simultáneos (ver real_path_armed):
    BOT_DRY_RUN=0   +   BOT_ALLOW_REAL=1   +   fichero ENABLE_REAL vigente
Así un despiste no puede provocar un fichaje real.

A diferencia del dashboard (que usa un token ADMIN solo para LEER al equipo),
este bot usa TU PROPIO token de sesión para FICHAR en tu
usuario → el fichaje queda registrado como tuyo, sin marca de "tercero".

Endpoint interno confirmado:
    POST https://back-eu1.sesametime.com/api/v3/employees/{TU_employeeId}/check-in
    POST .../check-out
    body: {"origin":"web","coordinates":{"latitude":<f>,"longitude":<f>},
           "workCheckTypeId": <null | id-de-pausa>}
"""

import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import ssl
import urllib.request
from urllib.error import HTTPError

log = logging.getLogger("sesame_client")

SESAME_BASE = os.environ.get("BOT_SESAME_BASE", "https://back-eu1.sesametime.com")
DRY_RUN = os.environ.get("BOT_DRY_RUN", "1") != "0"
ALLOW_REAL = os.environ.get("BOT_ALLOW_REAL", "0") == "1"
CONFIG_PATH = Path(os.environ.get("BOT_CONFIG", "config.json"))

# Tercer factor para armar el camino REAL (además de BOT_DRY_RUN=0 y BOT_ALLOW_REAL=1):
# un fichero ENABLE_REAL con caducidad. `touch ENABLE_REAL` abre una ventana de
# ENABLE_REAL_TTL segundos; pasado ese tiempo, el camino real vuelve a quedar desarmado.
ENABLE_REAL_FILE = Path(os.environ.get("BOT_ENABLE_REAL_FILE", "ENABLE_REAL"))
ENABLE_REAL_TTL = int(os.environ.get("BOT_ENABLE_REAL_TTL_SECONDS", "3600"))

# workBreakId del "Descanso" (confirmado en real; sale de tus checks reales, no de
# assigned-work-check-types). Se resuelve vía get_setting("pause_check_type_id"),
# que ya cubre env+config.

_ENDPOINT = {
    "CLOCK_IN":    ("check-in",  False),
    "CLOCK_OUT":   ("check-out", False),
    # Empezar pausa: POST .../pause con workBreakId (workCheckTypeId=null).
    "PAUSE_START": ("pause",     True),
    # Terminar pausa = reanudar trabajo: es un check-in normal (confirmado por captura
    # del navegador: al volver de la pausa Sesame llama a /check-in, no a /pause).
    "PAUSE_END":   ("check-in",  False),
}


def load_config(path: Path | str | None = None) -> dict:
    """Carga config local gitignored. Env vars siguen siendo la fuente prioritaria."""
    cfg_path = Path(path or CONFIG_PATH)
    if not cfg_path.exists():
        return {}
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_setting(name: str, default=None, config: dict | None = None):
    env_name = f"BOT_{name.upper()}"
    if env_name in os.environ:
        return os.environ[env_name]
    cfg = config if config is not None else load_config()
    return cfg.get(name, default)


def is_configured(value) -> bool:
    """True si un campo de config está relleno y no es un placeholder PEGA_AQUI/TU_."""
    text = str(value or "").strip()
    return bool(text) and not text.startswith(("PEGA_AQUI", "TU_"))


def require_read_config(purpose: str = "leer Sesame") -> dict | None:
    """Carga config.json y valida las credenciales de lectura.

    Imprime qué falta y devuelve None si no está lista; si todo OK devuelve el
    dict de config. Centraliza la validación que antes repetían los probe_*.py.
    """
    cfg_path = Path("config.json")
    if not cfg_path.exists():
        raise SystemExit("Falta config.json.")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    pending = [k for k in ("csid", "employee_id") if not is_configured(cfg.get(k))]
    if not is_configured(cfg.get("sesame_token")) and not is_configured(cfg.get("usid")):
        pending.append("sesame_token o usid")
    if pending:
        print(f"Faltan campos para {purpose}:")
        for key in pending:
            print(f"- {key}")
        print("No se ha llamado a Sesame.")
        return None
    return cfg


def get_auth(config: dict | None = None) -> dict:
    cfg = config if config is not None else load_config()
    return {
        "token": get_setting("sesame_token", config=cfg),
        "usid": get_setting("usid", config=cfg),
        "csid": get_setting("csid", config=cfg),
        "esid": get_setting("esid", config=cfg),
    }


def get_coordinates(config: dict | None = None):
    cfg = config if config is not None else load_config()
    raw = cfg.get("coordinates")
    if not raw:
        lat = os.environ.get("BOT_LATITUDE")
        lon = os.environ.get("BOT_LONGITUDE")
        return (float(lat), float(lon)) if lat and lon else None
    return (raw.get("latitude"), raw.get("longitude"))


def _resolve_endpoint(action: str):
    """Devuelve (path, work_break_id). work_break_id solo se usa en pausas."""
    if action not in _ENDPOINT:
        raise ValueError(f"Acción desconocida: {action}")
    path, is_break = _ENDPOINT[action]
    if not is_break:
        return path, None

    # `pause_check_type_id` en config contiene en realidad el workBreakId del Descanso.
    break_id = get_setting("pause_check_type_id")
    if break_id:
        return path, break_id
    if DRY_RUN:
        return path, "PENDING_WORK_BREAK_ID"
    raise RuntimeError("Falta pause_check_type_id (workBreakId del Descanso) para las pausas.")


def _body(coords, work_break_id=None):
    """Cuerpo del POST. Trabajo: workCheckTypeId=null. Pausa: además workBreakId."""
    lat, lon = (coords or (None, None))
    body = {"origin": "web",
            "coordinates": {"latitude": lat, "longitude": lon},
            "workCheckTypeId": None}
    if work_break_id:
        body["workBreakId"] = work_break_id
    return body


def enable_real_token_valid() -> tuple[bool, str]:
    """Tercer factor: el fichero ENABLE_REAL debe existir y no estar caducado.

    Devuelve (ok, motivo). `touch ENABLE_REAL` abre una ventana de ENABLE_REAL_TTL
    segundos; pasada, vuelve a quedar desarmado. Es un acto deliberado, no un env
    var olvidado.
    """
    if not ENABLE_REAL_FILE.exists():
        return False, "falta el fichero ENABLE_REAL"
    try:
        age = time.time() - ENABLE_REAL_FILE.stat().st_mtime
    except OSError as e:
        return False, f"no se puede leer ENABLE_REAL: {e}"
    if age > ENABLE_REAL_TTL:
        return False, f"ENABLE_REAL caducado (hace {int(age)}s, máximo {ENABLE_REAL_TTL}s)"
    return True, ""


def real_path_armed() -> tuple[bool, str]:
    """¿Está armado el camino REAL? Exige los 3 factores. Devuelve (ok, motivo)."""
    if DRY_RUN:
        return False, "dry-run"
    if not ALLOW_REAL:
        return False, "BOT_ALLOW_REAL=0"
    return enable_real_token_valid()


def execute_action(action: str, employee_id: str, coords=None, auth=None) -> dict:
    """Ejecuta UNA acción atómica. En dry-run solo registra y simula.
    `auth` = dict con el token/csid de SESIÓN DEL PROPIO usuario."""
    path, wct = _resolve_endpoint(action)
    url = f"{SESAME_BASE}/api/v3/employees/{employee_id}/{path}"
    body = _body(coords, wct)

    if DRY_RUN or not ALLOW_REAL:
        # Log redactado: ni coordenadas ni employeeId ni URL completa (RGPD / journald).
        log.info("DRY-RUN: no se llama a Sesame. Acción=%s endpoint=%s", action, path)
        return {"dry_run": True, "action": action, "url": url, "body": body, "ok": True}

    # --- Camino REAL: solo si los 3 factores están armados (gate del tercer factor). ---
    armed, reason = real_path_armed()
    if not armed:
        raise RuntimeError(
            f"Camino REAL no armado: {reason}. Para una prueba controlada: "
            f"`touch ENABLE_REAL` (ventana de {ENABLE_REAL_TTL}s) con BOT_DRY_RUN=0 y BOT_ALLOW_REAL=1."
        )
    if not coords or coords[0] is None or coords[1] is None:
        raise RuntimeError("Faltan coordenadas válidas para el fichaje real.")

    result = _real_post(url, body, auth or get_auth())
    status = result.get("status")
    return {"dry_run": False, "action": action, "status": status,
            "ok": status is not None and 200 <= status < 300}


def execute_plan(actions, employee_id, coords=None, auth=None) -> list:
    """Ejecuta las acciones EN ORDEN. Si una falla, NO aborta con excepción:
    devuelve lo ya ejecutado más un resultado con ok=False y el motivo, y se
    detiene (no hay rollback). Así el bot puede avisar de un plan a medias en vez
    de mostrar un "✅" engañoso.
    """
    cfg = load_config()
    coords = coords if coords is not None else get_coordinates(cfg)
    auth = auth if auth is not None else get_auth(cfg)
    results = []
    for a in actions:
        try:
            res = execute_action(a, employee_id, coords, auth)
        except Exception as e:  # noqa: BLE001
            results.append({"action": a, "ok": False, "error": str(e)[:200]})
            break
        results.append(res)
        if not res.get("ok", False):
            break
    return results


def get_current_state(employee_id: str, auth=None, state_url_template: str | None = None) -> str:
    """Lee el estado actual desde Sesame y lo normaliza a out/working/paused/remote.

    En dry-run mantiene el comportamiento anterior para poder probar sin red. Para
    lecturas reales hace falta configurar BOT_STATE_URL_TEMPLATE o state_url_template
    en config.json. La plantilla puede usar {base} y {employee_id}.
    """
    if DRY_RUN:
        return os.environ.get("BOT_FAKE_STATE", "out")

    cfg = load_config()
    template = state_url_template or get_setting("state_url_template", config=cfg)
    if not template:
        # Ventana de AYER a HOY: un turno que cruza medianoche tiene su checkIn abierto
        # archivado en el día de ayer. Si solo miráramos "hoy", a las 00:01 veríamos
        # "fuera" y un `fichar` provocaría un segundo check-in (doble fichaje). Leer
        # también ayer deja que classify_state_from_checks recoja el tramo abierto.
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        return classify_state_from_checks(
            get_checks(employee_id, from_day=yesterday, auth=auth or get_auth(cfg))
        )

    url = template.format(base=SESAME_BASE, employee_id=employee_id)
    payload = _real_get_json(url, auth or get_auth(cfg))
    return classify_state(payload)


def get_assigned_work_check_types(employee_id: str, auth=None) -> list:
    """Lee tipos de pausa/asistencia asignados al empleado. Solo GET."""
    cfg = load_config()
    url = f"{SESAME_BASE}/api/v3/employees/{employee_id}/assigned-work-check-types"
    payload = _real_get_json(url, auth or get_auth(cfg))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "items", "workCheckTypes", "assignedWorkCheckTypes"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def get_checks(employee_id: str, from_day: str | None = None, to_day: str | None = None, auth=None):
    """Lee checks de Sesame para un rango. Solo GET."""
    cfg = load_config()
    start = from_day or date.today().isoformat()
    end = to_day or start
    url = (
        f"{SESAME_BASE}/api/v3/employees/{employee_id}/checks"
        f"?from={start}&to={end}&includeOut=true"
    )
    return _real_get_json(url, auth or get_auth(cfg))


def classify_state_from_checks(payload) -> str:
    checks = _extract_list(payload)
    open_checks = [
        item for item in checks
        if isinstance(item, dict)
        and _present(item.get("checkIn"))
        and not _present(item.get("checkOut"))
    ]
    if not open_checks:
        return "out"

    current = open_checks[-1]
    if _present(current.get("workBreak")) or _present(current.get("workBreakId")):
        return "paused"
    if current.get("isRemote"):
        return "remote"
    return "working"


def summarize_checks_today(employee_id: str, auth=None) -> list[str]:
    """Devuelve lineas de resumen de los fichajes de hoy. Solo GET."""
    payload = get_checks(employee_id, auth=auth)
    return format_checks_summary(payload)


def format_checks_summary(payload) -> list[str]:
    checks = _extract_list(payload)
    if not checks:
        return ["Sin fichajes hoy."]

    lines = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        start = _format_check_time(item.get("checkIn"))
        end = _format_check_time(item.get("checkOut")) or "abierto"
        label = _check_label(item)
        lines.append(f"{start} - {end} · {label}")
    return lines or ["Sin fichajes hoy."]


def find_break_candidates(payload) -> list[dict]:
    checks = _extract_list(payload)
    candidates = {}
    for item in checks:
        if not isinstance(item, dict):
            continue
        if not (_present(item.get("workBreak")) or _present(item.get("workBreakId"))):
            continue
        candidate_id = item.get("workBreakId") or _nested_id(item.get("workBreak"))
        label = _nested_label(item.get("workBreak")) or "Descanso"
        key = candidate_id or label
        candidates[key] = {"id": candidate_id, "label": label}
    return list(candidates.values())


def _check_label(item):
    if item.get("isRemote"):
        return "Remoto"  # mismo término que muestra la web de Sesame
    if _present(item.get("workBreak")) or _present(item.get("workBreakId")):
        return _nested_label(item.get("workBreak")) or "Descanso"
    return _nested_label(item.get("workCheckType")) or "Oficina"


def _nested_label(value):
    if not isinstance(value, dict):
        return ""
    for key in ("name", "title", "label", "description"):
        if value.get(key):
            return str(value[key])
    return ""


def _nested_id(value):
    if not isinstance(value, dict):
        return ""
    for key in ("id", "uuid", "workBreakId", "workCheckTypeId"):
        if value.get(key):
            return str(value[key])
    return ""


def _format_check_time(value):
    if not _present(value):
        return ""
    if isinstance(value, dict):
        for key in ("date", "time", "datetime", "createdAt", "updatedAt"):
            if value.get(key):
                return _format_time_value(value[key])
        for nested in value.values():
            formatted = _format_check_time(nested)
            if formatted:
                return formatted
        return ""
    return _format_time_value(value)


_DISPLAY_TZ_CACHE = None


def _display_tz():
    """Zona horaria para MOSTRAR horas al usuario (configurable con
    `display_timezone` en config / BOT_DISPLAY_TIMEZONE; por defecto Europe/Madrid).

    Sesame suele devolver timestamps en UTC; sin convertir, /hoy mostraría las horas
    desfasadas 1-2h. Devuelve None solo si el sistema no tiene tzdata (raro en Linux),
    en cuyo caso se imprime la hora tal cual viene.
    """
    global _DISPLAY_TZ_CACHE
    if _DISPLAY_TZ_CACHE is None:
        for name in (get_setting("display_timezone") or "Europe/Madrid", "Europe/Madrid"):
            try:
                _DISPLAY_TZ_CACHE = ZoneInfo(name)
                break
            except Exception:  # noqa: BLE001  (zona inválida o falta tzdata)
                continue
    return _DISPLAY_TZ_CACHE


def _format_time_value(value):
    text = str(value)
    if "T" in text:
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            dt = None
        if dt is not None:
            # Si el timestamp trae zona (p.ej. UTC con 'Z'), lo pasamos a la zona local
            # de visualización antes de imprimir la hora de pared. Sin esto, un fichaje
            # a las 11:00 (Madrid) devuelto como 09:00:00Z saldría como "09:00:00".
            tz = _display_tz()
            if dt.tzinfo is not None and tz is not None:
                dt = dt.astimezone(tz)
            return dt.strftime("%H:%M:%S")
    if len(text) >= 8 and text[2:3] == ":":
        return text[:8]
    return text


def _extract_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "items", "checks", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _present(value):
    return value is not None and value != "" and value != {}


def classify_state(payload) -> str:
    """Clasifica respuestas habituales de presencia sin acoplarse a una forma exacta."""
    record = _find_presence_record(payload)
    if record is None:
        return "out"

    text = " ".join(
        str(record.get(k, "")).lower()
        for k in ("status", "state", "type", "workCheckTypeName", "workCheckType")
    )
    if any(marker in text for marker in ("out", "finished", "closed", "inactive", "absent")):
        return "out"
    if "remote" in text or "teletrab" in text:
        return "remote"
    if "pause" in text or "pausa" in text or "break" in text:
        return "paused"
    if any(marker in text for marker in ("working", "trabajando", "active", "clock_in", "check-in")):
        return "working"

    if record.get("isPaused") or record.get("paused"):
        return "paused"
    if record.get("isRemote") or record.get("remote"):
        return "remote"
    if record.get("isWorking") or record.get("working") or record.get("active"):
        return "working"
    return "out"


def _find_presence_record(value):
    if isinstance(value, dict):
        for key in ("presence", "current", "currentCheck", "lastCheck", "data"):
            found = _find_presence_record(value.get(key))
            if found is not None:
                return found
        if any(
            k in value
            for k in (
                "status",
                "state",
                "type",
                "workCheckTypeName",
                "workCheckType",
                "isWorking",
                "isPaused",
                "isRemote",
                "remote",
                "paused",
                "working",
                "active",
            )
        ):
            return value
        for v in value.values():
            found = _find_presence_record(v)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_presence_record(item)
            if found is not None:
                return found
    return None


def _auth_headers(auth, extra=None) -> dict:  # pragma: no cover  (depende de Sesame)
    """Cabeceras de autenticación de sesión (csid + Bearer o cookie USID).

    Compartido por las lecturas (GET) y por el camino real de escritura (POST),
    para que ambos usen exactamente la misma auth ya validada en lectura.
    """
    token = (auth or {}).get("token")
    usid = (auth or {}).get("usid")
    csid = (auth or {}).get("csid")
    esid = (auth or {}).get("esid")
    if not csid or (not token and not usid):
        raise RuntimeError("Faltan sesame_token o usid, y csid, para hablar con Sesame.")

    headers = {"csid": csid}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if usid:
        headers["Cookie"] = f"USID={usid}"
    if esid:
        headers["esid"] = esid
    if extra:
        headers.update(extra)
    return headers


def _real_get_json(url, auth):  # pragma: no cover  (depende de Sesame)
    req = urllib.request.Request(url, method="GET", headers=_auth_headers(auth))
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except HTTPError as e:
        # No volcamos el body crudo de Sesame a la excepción/logs (puede llevar PII).
        raise RuntimeError(f"Sesame GET falló: HTTP {e.code}") from e


def _real_post(url, body, auth):  # pragma: no cover  (camino real, validado en producción)
    """Camino real aislado: POST directo a Sesame con TU sesión.

    Usa _auth_headers, así que admite Bearer o cookie USID igual que la lectura.
    """
    data = json.dumps(body).encode()
    headers = _auth_headers(auth, {"Content-Type": "application/json"})
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
        return {"status": r.status, "body": r.read().decode("utf-8", "replace")}
