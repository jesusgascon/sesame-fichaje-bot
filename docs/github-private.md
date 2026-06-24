# Subir a GitHub privado

El repo puede subirse a GitHub, pero nunca debe incluir secretos.

## Antes de subir

Comprobar estado:

```bash
git status --short --ignored
```

Debe aparecer como ignorado:

```text
!! config.json
!! audit.jsonl
!! dry_state.json
```

Buscar posibles secretos en ficheros versionables:

```bash
rg -n "USID=|telegram_token|sesame_token|usid|csid|authorized_chat_ids" \
  --glob '!config.json' \
  --glob '!audit.jsonl' \
  --glob '!dry_state.json'
```

Es normal que salgan referencias en docs o plantillas, pero no valores reales.

## Crear repo privado

Opcion desde la web:

1. Entra en GitHub.
2. Crea un repositorio nuevo.
3. Nombre sugerido:

```text
sesame-fichaje-bot
```

4. Visibilidad: `Private`.
5. No añadas README, .gitignore ni licencia desde GitHub, porque ya existen localmente.

## Conectar remoto

Ejemplo:

```bash
git remote add origin git@github.com:TU_USUARIO/sesame-fichaje-bot.git
git branch -M main
git push -u origin main
```

Si usas HTTPS:

```bash
git remote add origin https://github.com/TU_USUARIO/sesame-fichaje-bot.git
git branch -M main
git push -u origin main
```

## Que no se sube

Por `.gitignore`, no se suben:

```text
config.json
config.secrets.json
*.token
key.bin
.env
audit.jsonl
dry_state.json
```

## Despues de clonar en otro Linux

1. Copia `config.example.json` a `config.json`.
2. Rellena Telegram, Sesame y `authorized_chat_ids`.
3. Ejecuta:

```bash
python3 check_config.py
./run_real_state_dry_actions.sh --help
./run_real_state_dry_actions.sh
```

4. Si quieres servicio siempre encendido, sigue `docs/always-on.md`.
