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
  `back-eu1.sesametime.com` con tu token (Fase 2).
- `telegram_bot.py` — bot de Telegram (long-polling, sin dependencias).
- `config.example.json` — plantilla de config (cópiala a `config.json`, gitignored).

## Probar en simulación (sin red)
```bash
python3 state_machine.py        # tabla de decisiones
BOT_FAKE_STATE=working BOT_TEST_EMPLOYEE_ID=demo python3 -c \
  "import telegram_bot as b; b.handle(1, 'fichar')"   # (requiere token TG para enviar)
```

## Interruptores de seguridad
El modo real exige **ambos**: `BOT_DRY_RUN=0` **y** `BOT_ALLOW_REAL=1`. Y aun así
el camino real lanza error hasta la Fase 2.

## Estado / plan
Ver `PLAN.md`. Resumen:
- ✅ Viabilidad confirmada (endpoint interno acepta la sesión).
- ✅ Esqueleto dry-run (este repo).
- ⏳ Fase 2: emparejamiento OTP + almacén cifrado, `get_state` real, idempotencia,
  auditoría, kill switch, confirmar tipo de pausa, y **prueba real controlada**.

## Cumplimiento
Solo uso legítimo: reflejar **tu jornada real** (como la app de Sesame). No fichar a
terceros, no automatizar sin presencia real, no enmascarar el origen.
