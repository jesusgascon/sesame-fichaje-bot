import json
from pathlib import Path

import sesame_client


def missing(cfg, key):
    value = str(cfg.get(key) or "").strip()
    return not value or value.startswith("PEGA_AQUI")


def main():
    cfg_path = Path("config.json")
    if not cfg_path.exists():
        raise SystemExit("Falta config.json.")

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    pending = [key for key in ("csid", "employee_id") if missing(cfg, key)]
    if missing(cfg, "sesame_token") and missing(cfg, "usid"):
        pending.append("sesame_token o usid")
    if pending:
        print("Faltan campos para buscar pausas:")
        for key in pending:
            print(f"- {key}")
        print("No se ha llamado a Sesame.")
        return

    payload = sesame_client.get_checks(cfg["employee_id"])
    candidates = sesame_client.find_break_candidates(payload)
    if not candidates:
        print("No se encontraron descansos en los checks de hoy.")
        return

    print("Candidatos de pausa detectados en checks de hoy:")
    for item in candidates:
        print(f"- {item['label']}: {item['id'] or 'sin id visible'}")
    print("No se ha escrito nada en Sesame.")


if __name__ == "__main__":
    main()
