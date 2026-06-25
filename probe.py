"""CLI unificado de sondas de SOLO LECTURA sobre Sesame.

Uso:
    python3 probe.py state     # estado real actual (out/working/paused/remote)
    python3 probe.py types     # tipos de pausa/asistencia asignados
    python3 probe.py checks    # volcado de los checks de hoy (claves seguras)
    python3 probe.py pauses    # candidatos de id de pausa en los checks de hoy

Ninguna escribe en Sesame. Todas validan la config con
sesame_client.require_read_config y reutilizan el cliente (sin duplicar lógica).
Sustituye a los antiguos probe_sesame_*.py / probe_pause_candidates.py.
"""

import sys

import sesame_client


def _safe_keys(item):
    if not isinstance(item, dict):
        return []
    return sorted(k for k in item.keys() if k.lower() not in {"token", "cookie", "authorization"})


def probe_state(cfg):
    state = sesame_client.get_current_state(cfg["employee_id"])
    print(f"Estado real Sesame: {state}")


def probe_types(cfg):
    employee_id = cfg["employee_id"]
    print("Probando Sesame solo lectura...")
    types = sesame_client.get_assigned_work_check_types(employee_id)
    print(f"- assigned-work-check-types: OK ({len(types)} elementos)")
    if not types:
        print("No se han detectado tipos. Puede ser normal si Sesame responde vacio.")
        return
    print("Tipos detectados:")
    for item in types:
        label = sesame_client._nested_label(item) or "(sin nombre)"
        item_id = sesame_client._nested_id(item) or "sin id visible"
        print(f"- {label}: {item_id}")


def probe_checks(cfg):
    print("Leyendo checks de hoy en Sesame solo lectura...")
    payload = sesame_client.get_checks(cfg["employee_id"])
    items = sesame_client._extract_list(payload)
    print(f"- respuesta: {type(payload).__name__}")
    if isinstance(payload, dict):
        print(f"- claves raiz: {', '.join(sorted(payload.keys()))}")
    print(f"- checks detectados: {len(items)}")
    for idx, item in enumerate(items, start=1):
        print(f"- check {idx} claves: {', '.join(_safe_keys(item))}")
        if not isinstance(item, dict):
            continue
        summary = {
            key: item.get(key)
            for key in ("date", "createdAt", "updatedAt", "isRemote", "isRemunerated")
            if key in item
        }
        summary["hasCheckIn"] = sesame_client._present(item.get("checkIn"))
        summary["hasCheckOut"] = sesame_client._present(item.get("checkOut"))
        summary["hasWorkBreak"] = (
            sesame_client._present(item.get("workBreak"))
            or sesame_client._present(item.get("workBreakId"))
        )
        label = (
            sesame_client._nested_label(item.get("workCheckType"))
            or sesame_client._nested_label(item.get("workBreak"))
        )
        if label:
            summary["label"] = label
        print(f"  resumen: {summary}")


def probe_pauses(cfg):
    payload = sesame_client.get_checks(cfg["employee_id"])
    candidates = sesame_client.find_break_candidates(payload)
    if not candidates:
        print("No se encontraron descansos en los checks de hoy.")
        return
    print("Candidatos de pausa detectados en checks de hoy:")
    for item in candidates:
        print(f"- {item['label']}: {item['id'] or 'sin id visible'}")
    print("No se ha escrito nada en Sesame.")


PROBES = {
    "state": ("estado real actual", probe_state),
    "types": ("tipos de pausa/asistencia asignados", probe_types),
    "checks": ("volcado de checks de hoy", probe_checks),
    "pauses": ("candidatos de id de pausa", probe_pauses),
}


def _usage():
    print("Uso: python3 probe.py <state|types|checks|pauses>")
    for name, (desc, _) in PROBES.items():
        print(f"  {name:7} {desc}")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return
    name = argv[0]
    if name not in PROBES:
        raise SystemExit(f"Sonda desconocida: {name}. Usa: {', '.join(PROBES)}")
    desc, fn = PROBES[name]
    cfg = sesame_client.require_read_config(f"sonda '{name}' ({desc})")
    if cfg is None:
        return
    fn(cfg)


if __name__ == "__main__":
    main(sys.argv[1:])
