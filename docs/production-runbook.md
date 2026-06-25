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

```bash
./run_real.sh
```

Ficha de verdad. Aun asi, el POST real solo ocurre con los 3 factores armados
(BOT_DRY_RUN=0 + BOT_ALLOW_REAL=1 + fichero ENABLE_REAL vigente) y el chat vinculado por
OTP; si falta alguno, no ficha. Ver "Activar el modo real" mas abajo y `docs/security.md`.

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

## Activar el modo real (validado en v1.0.0)

El modo real ya esta validado (fichar y pausar reales). El camino real exige 3 factores
+ binding OTP (ver `docs/security.md`). Procedimiento para armarlo / primera vez:

1. `./secure_perms.sh` (permisos 600 en config y estado).
2. `/sesion` en verde y confirmar que estas realmente fuera de jornada.
3. `/vincular` y leer el codigo en la consola del servidor:
   `journalctl --user -u sesame-fichaje-bot.service -f | grep VINCULACION`.
   Escribir el codigo en Telegram. `/modo` debe decir "Chat vinculado: si".
4. Arrancar con `BOT_DRY_RUN=0` y `BOT_ALLOW_REAL=1`.
5. Armar el tercer factor: `./arm_real.sh` (ventana corta, caduca sola).
   `/modo` debe decir "Camino real armado: si".
6. Enviar `fichar`, confirmar SI, y comprobar que aparece la entrada en Sesame.
7. Enviar `fichar` de nuevo para cerrar. Verificar `/hoy`.
8. `./arm_real.sh off` al terminar.

Hasta entonces, produccion recomendada = estado real + acciones simuladas.
