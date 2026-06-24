import json
from pathlib import Path


SENSITIVE = {
    "telegram_token": "token de Telegram",
    "sesame_token": "token de Sesame",
    "usid": "cookie USID de Sesame",
    "csid": "csid de Sesame",
    "esid": "esid de Sesame",
    "employee_id": "employeeId de Sesame",
}


def present(value):
    return bool(str(value or "").strip()) and not str(value).startswith("PEGA_AQUI")


def main():
    path = Path("config.json")
    if not path.exists():
        raise SystemExit("Falta config.json.")

    cfg = json.loads(path.read_text(encoding="utf-8"))
    print("Configuracion local:")
    for key, label in SENSITIVE.items():
        status = "OK" if present(cfg.get(key)) else "PENDIENTE"
        print(f"- {label}: {status}")
    if present(cfg.get("sesame_token")) or present(cfg.get("usid")):
        print("- autenticacion Sesame: OK")
    else:
        print("- autenticacion Sesame: PENDIENTE")

    state_template = cfg.get("state_url_template")
    print(f"- endpoint estado Sesame: {'OK' if present(state_template) else 'PENDIENTE'}")
    print(f"- id pausa/descanso: {'OK' if present(cfg.get('pause_check_type_id')) else 'PENDIENTE'}")
    authorized = cfg.get("authorized_chat_ids") or []
    print(f"- chats autorizados Telegram: {'OK' if authorized else 'PENDIENTE'}")
    print(f"- fichero auditoria: {cfg.get('audit_log') or 'audit.jsonl'}")
    print(f"- fichero estado simulacion: {cfg.get('dry_state_file') or 'dry_state.json'}")
    print(f"- kill switch: {'ACTIVO' if cfg.get('kill_switch') else 'apagado'}")


if __name__ == "__main__":
    main()
