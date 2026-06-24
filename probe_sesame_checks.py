import json
from pathlib import Path

import sesame_client


def missing(cfg, key):
    value = str(cfg.get(key) or "").strip()
    return not value or value.startswith("PEGA_AQUI")


def list_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "items", "checks", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def safe_keys(item):
    if not isinstance(item, dict):
        return []
    return sorted(k for k in item.keys() if k.lower() not in {"token", "cookie", "authorization"})


def present(value):
    return value is not None and value != "" and value != {}


def nested_label(value):
    if not isinstance(value, dict):
        return ""
    for key in ("name", "title", "label", "description"):
        if value.get(key):
            return str(value[key])
    return ""


def main():
    cfg_path = Path("config.json")
    if not cfg_path.exists():
        raise SystemExit("Falta config.json.")

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    pending = [key for key in ("csid", "employee_id") if missing(cfg, key)]
    if missing(cfg, "sesame_token") and missing(cfg, "usid"):
        pending.append("sesame_token o usid")
    if pending:
        print("Faltan campos para probar checks:")
        for key in pending:
            print(f"- {key}")
        print("No se ha llamado a Sesame.")
        return

    print("Leyendo checks de hoy en Sesame solo lectura...")
    payload = sesame_client.get_checks(cfg["employee_id"])
    items = list_items(payload)
    print(f"- respuesta: {type(payload).__name__}")
    if isinstance(payload, dict):
        print(f"- claves raiz: {', '.join(sorted(payload.keys()))}")
    print(f"- checks detectados: {len(items)}")
    for idx, item in enumerate(items, start=1):
        print(f"- check {idx} claves: {', '.join(safe_keys(item))}")
        if isinstance(item, dict):
            summary = {
                key: item.get(key)
                for key in ("date", "createdAt", "updatedAt", "isRemote", "isRemunerated")
                if key in item
            }
            summary["hasCheckIn"] = present(item.get("checkIn"))
            summary["hasCheckOut"] = present(item.get("checkOut"))
            summary["hasWorkBreak"] = present(item.get("workBreak")) or present(item.get("workBreakId"))
            label = nested_label(item.get("workCheckType")) or nested_label(item.get("workBreak"))
            if label:
                summary["label"] = label
            if summary:
                print(f"  resumen: {summary}")


if __name__ == "__main__":
    main()
