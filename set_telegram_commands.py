import json
import urllib.parse
import urllib.request

import sesame_client


COMMANDS = [
    {"command": "start", "description": "Ayuda inicial"},
    {"command": "fichar", "description": "Entrar o salir"},
    {"command": "pausar", "description": "Empezar o terminar descanso"},
    {"command": "estado", "description": "Ver estado actual"},
    {"command": "hoy", "description": "Ver fichajes de hoy"},
    {"command": "sesion", "description": "Comprobar sesión Sesame"},
    {"command": "modo", "description": "Ver modo de seguridad"},
    {"command": "vincular", "description": "Vincular este chat (codigo OTP por consola)"},
    {"command": "mi_chat_id", "description": "Ver tu chat_id para autorizarte"},
    {"command": "ayuda", "description": "Ayuda completa"},
]


def main():
    cfg = sesame_client.load_config()
    token = cfg.get("telegram_token")
    if not token or token == "PEGA_AQUI_EL_TOKEN_DE_BOTFATHER":
        raise SystemExit("Falta telegram_token en config.json.")

    data = urllib.parse.urlencode({"commands": json.dumps(COMMANDS)}).encode()
    url = f"https://api.telegram.org/bot{token}/setMyCommands"
    with urllib.request.urlopen(url, data=data, timeout=20) as response:
        payload = json.load(response)

    if not payload.get("ok"):
        raise SystemExit(f"Telegram no acepto comandos: {payload}")
    print("Comandos Telegram registrados: " + ", ".join("/" + c["command"] for c in COMMANDS))


if __name__ == "__main__":
    main()
