"""
Cliente de fichaje sobre Sesame (autónomo, con TU propio token).

SEGURIDAD POR DEFECTO: arranca en DRY-RUN. En dry-run NO se hace ninguna
petición a Sesame: solo se registra (log) "lo que se haría". Para ejecutar de
verdad hacen falta DOS interruptores a la vez:
    BOT_DRY_RUN=0   y   BOT_ALLOW_REAL=1
Así un despiste no puede provocar un fichaje real.

A diferencia del dashboard (que usa el token ADMIN de un compañero solo para
LEER al equipo), este bot usa TU PROPIO token de sesión para FICHAR en tu
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
import ssl
import urllib.request

log = logging.getLogger("sesame_client")

SESAME_BASE = os.environ.get("BOT_SESAME_BASE", "https://back-eu1.sesametime.com")
DRY_RUN = os.environ.get("BOT_DRY_RUN", "1") != "0"
ALLOW_REAL = os.environ.get("BOT_ALLOW_REAL", "0") == "1"

# Tipo de "pausa" en Sesame (de GET /api/v3/employees/{id}/assigned-work-check-types).
# TODO: confirmar el id real antes de usar pausas en real.
PAUSE_CHECK_TYPE_ID = os.environ.get("BOT_PAUSE_CHECK_TYPE_ID") or None

_ENDPOINT = {
    "CLOCK_IN":    ("check-in",  None),
    "CLOCK_OUT":   ("check-out", None),
    "PAUSE_START": ("check-in",  PAUSE_CHECK_TYPE_ID),
    "PAUSE_END":   ("check-out", PAUSE_CHECK_TYPE_ID),
}


def _body(coords, work_check_type_id):
    lat, lon = (coords or (None, None))
    return {"origin": "web",
            "coordinates": {"latitude": lat, "longitude": lon},
            "workCheckTypeId": work_check_type_id}


def execute_action(action: str, employee_id: str, coords=None, auth=None) -> dict:
    """Ejecuta UNA acción atómica. En dry-run solo registra y simula.
    `auth` = dict con el token/csid de SESIÓN DEL PROPIO usuario (Fase 2)."""
    if action not in _ENDPOINT:
        raise ValueError(f"Acción desconocida: {action}")
    path, wct = _ENDPOINT[action]
    url = f"{SESAME_BASE}/api/v3/employees/{employee_id}/{path}"
    body = _body(coords, wct)

    if DRY_RUN or not ALLOW_REAL:
        log.info("DRY-RUN: NO se llama a Sesame. Se haría: POST %s  body=%s",
                 url, json.dumps(body))
        return {"dry_run": True, "action": action, "url": url, "body": body, "ok": True}

    # --- Camino REAL (solo con BOT_DRY_RUN=0 y BOT_ALLOW_REAL=1) ---
    # Deshabilitado a propósito hasta completar la Fase 2 (emparejamiento OTP +
    # idempotencia + auditoría + kill switch + prueba controlada).
    raise RuntimeError("Camino REAL no habilitado todavía (Fase 2). Mantén BOT_ALLOW_REAL=0.")


def execute_plan(actions, employee_id, coords=None, auth=None) -> list:
    return [execute_action(a, employee_id, coords, auth) for a in actions]


def _real_post(url, body, token, csid):  # pragma: no cover  (reservado Fase 2)
    """Camino real aislado: POST directo a Sesame con TU token de sesión."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}", "csid": csid})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
        return {"status": r.status, "body": r.read().decode("utf-8", "replace")}
