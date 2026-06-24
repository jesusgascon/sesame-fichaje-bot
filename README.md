# sesame-fichaje-bot

Bot de **Telegram** para **fichar / pausar** en Sesame desde el móvil. Proyecto
**independiente** del dashboard `calendario-vacaciones` (que es de solo lectura):
aquí se **escribe** en Sesame, así que vive aparte para aislar el riesgo.

> ⚠️ **Por defecto NO ficha nada real.** Arranca en **dry-run** (simula y registra
> "lo que haría"). El camino real está deshabilitado en código hasta completar la
> Fase 2 de seguridad. Ver `PLAN.md`.

## Idea
Desde tu móvil escribes al bot `fichar` o `pausar` y el bot registra la acción en
**tu** usuario de Sesame (el que tiene tu móvil registrado). Lógica toggle: fichar
alterna inicio/fin de jornada; pausar alterna inicio/fin de pausa (ver tabla en
`state_machine.py`).

## Separación de credenciales (lo limpio)
- **Dashboard** → token **admin** de un compañero → solo **ver** al equipo.
- **Este bot** → **TU propio token** de sesión → solo **fichar en tu usuario**, de
  modo que el fichaje queda registrado como tuyo (sin marca de "tercero").

El fichaje se dirige por el `employeeId` de la URL
(`POST /api/v3/employees/{TU_id}/check-in`), así que siempre actúa sobre tu usuario.

## Piezas
- `state_machine.py` — lógica pura fichar/pausar. Pruébala: `python3 state_machine.py`.
- `sesame_client.py` — ejecuta las acciones (dry-run por defecto), directo a
  `back-eu1.sesametime.com` con tu token (Fase 2). Incluye lectura GET configurable
  para obtener el estado actual cuando se confirme el endpoint.
- `telegram_bot.py` — bot de Telegram (long-polling, sin dependencias).
  Mantiene confirmaciones con botones SI/NO y caducidad, rate-limit, lock por
  empleado, kill switch y auditoría local JSONL sin secretos.
- `config.example.json` — plantilla de config (cópiala a `config.json`, gitignored).

## Probar en simulación (sin red)
```bash
python3 state_machine.py        # tabla de decisiones
BOT_FAKE_STATE=working BOT_TEST_EMPLOYEE_ID=demo python3 -c \
  "import telegram_bot as b; b.handle(1, 'fichar')"   # (requiere token TG para enviar)
```

Ayuda rapida:

```bash
./help.sh
./run_dry_run.sh --help
./run_real_state_dry_actions.sh --help
```

## Arrancar el bot en Telegram, en simulacion
1. Crea el bot con `@BotFather` y copia el token.
2. Pega el token en `config.json`, campo `telegram_token`.
3. Ejecuta:
```bash
./run_dry_run.sh
```

Mientras esté abierto ese proceso, el bot responderá en Telegram. Si cierras la
terminal o apagas el ordenador, el bot deja de responder. Para dejarlo siempre
encendido lo convertiremos en servicio cuando el flujo de prueba esté validado.

## Interruptores de seguridad
El modo real exige **ambos**: `BOT_DRY_RUN=0` **y** `BOT_ALLOW_REAL=1`. Y aun así
el camino real lanza error hasta la Fase 2.

## Estado / plan
Ver `PLAN.md`. Resumen:
- ✅ Viabilidad confirmada (endpoint interno acepta la sesión).
- ✅ Esqueleto dry-run (este repo).
- ⏳ Fase 2: emparejamiento OTP + almacén cifrado, `get_state` real, idempotencia,
  auditoría, kill switch, confirmar tipo de pausa, y **prueba real controlada**.

### Estado real
En dry-run, `/estado` sigue usando `BOT_FAKE_STATE`. Para lectura real hay que rellenar
`state_url_template` en `config.json` con el endpoint GET confirmado de Sesame. La
plantilla admite `{base}` y `{employee_id}`.

### Guardas locales
`BOT_KILL_SWITCH=1` bloquea acciones. `audit_log`/`BOT_AUDIT_LOG` define el fichero
JSONL de auditoría, gitignored por defecto. Las confirmaciones caducan en 120s y el
bot relee el estado justo antes de ejecutar para evitar acciones antiguas. En
simulación, `/reset` vuelve el estado a `out`.

Para revisar qué falta por configurar sin imprimir secretos:
```bash
python3 check_config.py
```

Para probar Sesame solo lectura cuando `csid`, `employee_id` y una forma de sesion
esten rellenos en `config.json`:
```bash
python3 probe_sesame_readonly.py
python3 probe_sesame_state.py
python3 probe_pause_candidates.py
```

Si en Network aparece `Authorization: Bearer ...`, pega el valor sin `Bearer` en
`sesame_token`. Si no aparece Authorization, pega la cookie `USID` en `usid`.

Para arrancar Telegram leyendo estado real de Sesame, pero manteniendo acciones
simuladas:
```bash
./run_real_state_dry_actions.sh
```

En ese modo `/estado` y `/hoy` son lecturas reales de Sesame; `fichar` y `pausar`
siguen simulados mientras `BOT_ALLOW_REAL=0`.

`/modo` muestra desde Telegram si el bot esta en simulacion, estado real con
acciones simuladas, o modo real.

Para renovar o comprobar la sesion de Sesame, ver
[`docs/sesame-session.md`](docs/sesame-session.md). Desde Telegram, `/sesion`
comprueba si la sesion sigue viva sin mostrar secretos.

Para autorizar el chat de Telegram que puede usar el bot, ver
[`docs/telegram-auth.md`](docs/telegram-auth.md). Usa `/mi_chat_id` y añade ese
valor a `authorized_chat_ids` en `config.json`.

Para dejar el bot siempre encendido como servicio de usuario, ver
[`docs/always-on.md`](docs/always-on.md).

Guias operativas:

- [`docs/production-runbook.md`](docs/production-runbook.md) — arrancar, parar,
  servicio, logs y camino a prueba real.
- [`docs/telegram-usage.md`](docs/telegram-usage.md) — como abrir y usar el bot en
  Telegram.
- [`docs/sesame-origin.md`](docs/sesame-origin.md) — como se vera el origen del
  fichaje en Sesame.
- [`docs/github-private.md`](docs/github-private.md) — como subirlo a un repositorio
  privado sin secretos.

## Cumplimiento
Solo uso legítimo: reflejar **tu jornada real** (como la app de Sesame). No fichar a
terceros, no automatizar sin presencia real, no enmascarar el origen.
