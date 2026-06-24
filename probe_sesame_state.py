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
        print("Faltan campos para leer estado real:")
        for key in pending:
            print(f"- {key}")
        print("No se ha llamado a Sesame.")
        return

    state = sesame_client.get_current_state(cfg["employee_id"])
    print(f"Estado real Sesame: {state}")


if __name__ == "__main__":
    main()
