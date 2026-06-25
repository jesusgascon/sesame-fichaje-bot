# GitHub privado

> **Estado actual:** el repo YA está en GitHub privado:
> `https://github.com/jesusgascon/sesame-fichaje-bot` (remoto `origin`, rama **`master`**).
> Esta guía sirve para (a) comprobar antes de cada push que no se cuela ningún secreto,
> y (b) reconfigurar el remoto si clonas en otra máquina. **No** vuelvas a ejecutar
> `git remote add` ni `git branch -M main`: cambiaría la rama y rompería el upstream.

El repo nunca debe incluir secretos.

## Antes de cada push

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

Buscar posibles secretos en ficheros versionables (usa `git grep`, que solo mira lo
trackeado; si tienes `rg` instalado, vale igual):

```bash
git grep -n -E "USID=|telegram_token|sesame_token|usid|csid|authorized_chat_ids"
```

Es normal que salgan referencias en docs o plantillas, pero no valores reales.

## Push del día a día

El remoto ya está configurado. Con permiso explícito de Jesús:

```bash
git push origin master
```

## Reconectar remoto (solo si clonas en otra máquina)

Si el remoto no existiera en una copia nueva:

```bash
git remote add origin https://github.com/jesusgascon/sesame-fichaje-bot.git
git push -u origin master
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
