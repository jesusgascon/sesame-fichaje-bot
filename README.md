# sesame-fichaje-bot

Bot de **Telegram** para **fichar / pausar** en Sesame desde el móvil. Proyecto
**independiente** del dashboard `calendario-vacaciones` (que es de solo lectura):
aquí se **escribe** en Sesame, así que vive aparte para aislar el riesgo.

> 📖 **¿Buscas cómo usarlo?** Manual completo en
> **[`docs/guia-completa.md`](docs/guia-completa.md)** (comandos, puesta en marcha,
> pausas, herramientas, resolución de problemas).

> ✅ **v1.0.0 — en producción.** El bot ficha de verdad (jornadas y pausas) en tu
> usuario y corre como **servicio systemd** (siempre encendido). Modo real validado
> en real (2026-06-25). Arranca **seguro por defecto**: el camino real exige 3 factores
> y está **desarmado** hasta que lo armes (ver "Interruptores de seguridad" y
> `docs/security.md`).

## Idea
Desde tu móvil escribes al bot `fichar` o `pausar` y el bot registra la acción en
**tu** usuario de Sesame (el que tiene tu móvil registrado). Lógica toggle: fichar
alterna inicio/fin de jornada; pausar alterna inicio/fin de pausa (ver tabla en
`state_machine.py`).

## Separación de credenciales (lo limpio)
- **Dashboard** → un token **admin** → solo **ver** al equipo.
- **Este bot** → **TU propio token** de sesión → solo **fichar en tu usuario**, de
  modo que el fichaje queda registrado como tuyo (sin marca de "tercero").

El fichaje se dirige por el `employeeId` de la URL
(`POST /api/v3/employees/{TU_id}/check-in`), así que siempre actúa sobre tu usuario.

## Piezas
- `state_machine.py` — lógica pura fichar/pausar. Pruébala: `python3 state_machine.py`.
- `sesame_client.py` — ejecuta las acciones (dry-run por defecto; modo real armado en
  producción), directo a `back-eu1.sesametime.com` con tu token. Lee el estado real de
  `GET /api/v3/employees/{id}/checks` (endpoint confirmado).
- `telegram_bot.py` — bot de Telegram (long-polling, sin dependencias).
  Mantiene confirmaciones con botones SI/NO y caducidad, rate-limit, lock por
  empleado, kill switch y auditoría local JSONL sin secretos.
- `link_store.py` — almacén persistente (JSON) del vínculo chat↔empleado, emparejado
  por OTP desde consola (`/vincular`).
- `config.example.json` — plantilla de config (cópiala a `config.json`, gitignored).

## Tests (sin red)
```bash
./run_tests.sh        # suite unittest (stdlib): state machine, clasificación,
                      # LinkStore y flujo del bot con send inyectado. Todo en dry-run.
```

## Probar en simulación (sin red, opcional)
> El proyecto está en producción en modo real. Esta sección es solo para desarrollo/pruebas locales.

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

## Arrancar el bot en Telegram (simulacion, para pruebas)
1. Crea el bot con `@BotFather` y copia el token.
2. Pega el token en `config.json`, campo `telegram_token`.
3. Ejecuta:
```bash
./run_dry_run.sh
```

Mientras esté abierto ese proceso, el bot responderá en Telegram en dry-run. Si cierras
la terminal o apagas el ordenador, el bot deja de responder.

**En producción** el bot ya corre como **servicio systemd** (siempre encendido, modo
real). Para arrancar/parar/ver logs en producción, ver
[`docs/production-runbook.md`](docs/production-runbook.md) y `docs/always-on.md`.

## Interruptores de seguridad
El modo real exige **3 factores a la vez** — `BOT_DRY_RUN=0`, `BOT_ALLOW_REAL=1` y el
fichero `ENABLE_REAL` vigente (`./arm_real.sh`) — **y** que el chat esté vinculado por
OTP (`/vincular`). Desarmado por defecto: sin todo eso, no ficha. Detalle completo en
[`docs/security.md`](docs/security.md). Asegura permisos con `./secure_perms.sh`.

## Estado / plan
Ver `PLAN.md` y `docs/security.md`. Resumen:
- ✅ Viabilidad confirmada (endpoint interno acepta la sesión).
- ✅ Dry-run + `get_state` real + tests (stdlib).
- ✅ Fase 2/seguridad: emparejamiento OTP (consola), gate R1, idempotencia (flock +
  dedupe), auditoría endurecida, kill switch en caliente, permisos 600, 3er factor.
- ✅ **Modo real validado** (v1.0.0): fichar (jornadas) y pausar (descansos) en real,
  contratos de Sesame confirmados (check-in/out y `/pause` + `workBreakId`).

### Estado real
En dry-run, `/estado` sigue usando `BOT_FAKE_STATE`. Fuera de dry-run, el estado real se
obtiene automáticamente de `GET /api/v3/employees/{id}/checks` (clasificando los tramos
abiertos). `state_url_template` en `config.json` es un **override opcional** (admite
`{base}` y `{employee_id}`) por si quisieras forzar otro endpoint GET; si lo dejas
vacío/null, se usa el camino de `/checks`.

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
python3 probe.py state     # estado real actual
python3 probe.py types     # tipos de pausa/asistencia asignados
python3 probe.py checks    # volcado de los checks de hoy
python3 probe.py pauses    # candidatos de id de pausa
python3 set_telegram_commands.py
```

Si en Network aparece `Authorization: Bearer ...`, pega el valor sin `Bearer` en
`sesame_token`. Si no aparece Authorization, pega la cookie `USID` en `usid`.

Para arrancar Telegram leyendo estado real de Sesame, pero manteniendo acciones
simuladas:
```bash
./run_real_state_dry_actions.sh
```

En ese modo `/estado` y `/hoy` son lecturas reales de Sesame; `/fichar` y `/pausar`
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

- [`docs/guia-completa.md`](docs/guia-completa.md) — **manual completo**: comandos,
  puesta en marcha, pausas, modos, herramientas y resolucion de problemas.
- [`docs/security.md`](docs/security.md) — modelo de seguridad: OTP, 3er factor,
  gate R1, idempotencia, auditoria, permisos 600 y checklist de prueba real.
- [`docs/production-runbook.md`](docs/production-runbook.md) — arrancar, parar,
  servicio, logs y camino a prueba real.
- [`docs/telegram-usage.md`](docs/telegram-usage.md) — como abrir y usar el bot en
  Telegram.
- [`docs/sesame-origin.md`](docs/sesame-origin.md) — como se vera el origen del
  fichaje en Sesame.
- [`docs/siri-shortcuts.md`](docs/siri-shortcuts.md) — como preparar Atajos/Siri
  para abrir el bot y usar comandos slash.
- [`docs/github-private.md`](docs/github-private.md) — como subirlo a un repositorio
  privado sin secretos.

## Cumplimiento
Solo uso legítimo: reflejar **tu jornada real** (como la app de Sesame). No fichar a
terceros, no automatizar sin presencia real, no enmascarar el origen.
