# Runbook de produccion

Esta guia describe como operar el bot en Linux.

## Modos

### Simulacion pura

```bash
./run_dry_run.sh
```

Uso:

- probar Telegram
- probar comandos
- no usa Sesame real
- no ficha real

### Preproduccion segura

```bash
./run_real_state_dry_actions.sh
```

Uso recomendado ahora:

- `/estado` lee Sesame real
- `/hoy` lee fichajes reales de hoy
- `/sesion` comprueba la sesion real
- `fichar` y `pausar` no escriben en Sesame

### Produccion real

Todavia no esta habilitada. Aunque pongas variables de entorno, el codigo sigue
bloqueando el POST real hasta hacer una prueba controlada y revisar las guardas.

## Ayuda en linea

```bash
./help.sh
./run_dry_run.sh --help
./run_real_state_dry_actions.sh --help
```

## Comprobar antes de arrancar

```bash
python3 check_config.py
python3 probe.py state
python3 probe.py types
python3 probe.py pauses
```

Esperado (salida de `check_config.py`):

```text
token de Telegram: OK
cookie USID de Sesame: OK
csid de Sesame: OK
esid de Sesame: OK
employeeId de Sesame: OK
autenticacion Sesame: OK
endpoint estado Sesame: PENDIENTE   (opcional: hay fallback a /checks)
id pausa/descanso: OK
chats autorizados Telegram: OK
```

## Arrancar en terminal

```bash
./run_real_state_dry_actions.sh
```

Parar:

```text
Ctrl+C
```

## Arrancar como servicio

```bash
mkdir -p ~/.config/systemd/user
cp deploy/sesame-fichaje-bot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable sesame-fichaje-bot.service
systemctl --user start sesame-fichaje-bot.service
```

Ver estado:

```bash
systemctl --user status sesame-fichaje-bot.service
```

Ver logs:

```bash
journalctl --user -u sesame-fichaje-bot.service -f
```

Parar:

```bash
systemctl --user stop sesame-fichaje-bot.service
```

Reiniciar:

```bash
systemctl --user restart sesame-fichaje-bot.service
```

## Al cambiar config.json

Si el bot corre en terminal:

```text
Ctrl+C
./run_real_state_dry_actions.sh
```

Si corre como servicio:

```bash
systemctl --user restart sesame-fichaje-bot.service
```

## Si caduca la sesion de Sesame

1. Abre Sesame en el navegador.
2. Obtén de nuevo `usid`, `csid` y `esid`.
3. Actualiza `config.json`.
4. Reinicia el bot.

Ver detalles en `docs/sesame-session.md`.

## Prueba real controlada

No hacer hasta aprobarlo expresamente.

La prueba real minima seria:

1. Confirmar que estas realmente fuera de jornada.
2. Activar camino real en codigo.
3. Arrancar con `BOT_DRY_RUN=0` y `BOT_ALLOW_REAL=1`.
4. Enviar `fichar`.
5. Confirmar que aparece entrada en Sesame.
6. Enviar `fichar` de nuevo para cerrar.
7. Verificar `/hoy`.

Hasta entonces, produccion recomendada = estado real + acciones simuladas.
