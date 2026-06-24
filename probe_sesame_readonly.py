import json
from pathlib import Path

import sesame_client


def missing(cfg, key):
    value = str(cfg.get(key) or "").strip()
    return not value or value.startswith("PEGA_AQUI")


def label_for(item):
    if not isinstance(item, dict):
        return str(item)
    for key in ("name", "title", "label", "description"):
        if item.get(key):
            return str(item[key])
    return "(sin nombre)"


def id_for(item):
    if not isinstance(item, dict):
        return ""
    for key in ("id", "workCheckTypeId", "uuid"):
        if item.get(key):
            return str(item[key])
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
        print("Faltan campos para probar Sesame solo lectura:")
        for key in pending:
            print(f"- {key}")
        print("No se ha llamado a Sesame.")
        return

    employee_id = cfg["employee_id"]
    print("Probando Sesame solo lectura...")
    print("- credenciales: presentes")
    print("- employeeId: presente")
    types = sesame_client.get_assigned_work_check_types(employee_id)
    print(f"- assigned-work-check-types: OK ({len(types)} elementos)")
    if types:
        print("Tipos detectados:")
        for item in types:
            item_id = id_for(item)
            label = label_for(item)
            print(f"- {label}: {item_id or 'sin id visible'}")
    else:
        print("No se han detectado tipos. Puede ser normal si Sesame responde vacio.")


if __name__ == "__main__":
    main()
