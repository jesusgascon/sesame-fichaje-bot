# CLAUDE.md — Contexto del proyecto (léeme al iniciar)

> Este fichero lo lee Claude Code automáticamente al abrir una sesión en esta
> carpeta. Resume TODO lo necesario para continuar sin la conversación previa.
> Si algo aquí contradice al código, manda el código (verifícalo).

---

## 0. Qué es esto y de dónde viene

**`sesame-fichaje-bot`** = bot de **Telegram** para **fichar / pausar** en Sesame HR
desde el móvil. Es un proyecto **independiente** del dashboard `calendario-vacaciones`
(otra carpeta/repo, en `../calendario-vacaciones`).

- **Dashboard** (`calendario-vacaciones`, rama `master`): web de **solo LECTURA**;
  ve a todo el equipo usando un **token admin**. **NO se toca desde
  aquí.** Su trabajo va en SU propia conversación.
- **Este repo**: **ESCRIBE** en Sesame (crea fichajes). Por eso vive aparte: aísla el
  riesgo (legal/seguridad) del dashboard de solo-lectura.

El usuario es **Jesús Gascón Gómez** (jesusgascon@gmail.com). Habla en español.
Director del proyecto = Jesús; Claude propone y ejecuta, pero **las decisiones grandes
se aprueban juntos antes**.

---

## 1. Reglas duras (no las rompas)

1. **Ninguna prueba real hecha todavía.** El bot arranca en **dry-run**. El camino real
   YA existe pero está **desarmado por defecto**: exige 3 factores simultáneos
   (`BOT_DRY_RUN=0` + `BOT_ALLOW_REAL=1` + fichero `ENABLE_REAL` vigente, ver
   `./arm_real.sh`) **y** un chat vinculado por OTP. Sin todo eso, `execute_action`
   lanza error y no ficha. La **primera prueba real** requiere OK explícito de Jesús
   (ver checklist en `docs/security.md`).
2. **No commits/push sin permiso explícito** de Jesús (cada vez). El repo está en
   **GitHub PRIVADO** (`github.com/jesusgascon/sesame-fichaje-bot`, rama `master`).
   Publicar/pushear cambios requiere su OK explícito cada vez. Nunca subir secretos.
3. **Limpieza y orden siempre** (borrar ramas/temporales tras fusionar, no dejar restos).
4. **No exponer secretos.** Nunca pegar/guardar el token de sesión, cookies, csid, ni el
   móvil/employeeId real en claro, ni en commits. `config.json` está gitignored.
5. **Uso legítimo únicamente:** el bot refleja la **jornada REAL** de Jesús (igual que la
   app oficial de Sesame). Prohibido: fichar a terceros, automatizar sin presencia real,
   enmascarar el origen del fichaje.

---

## 2. Viabilidad — CONFIRMADA (lo más importante)

Con la **licencia actual** de Sesame:
- La **API oficial** `https://api-eu1.sesametime.com/schedule/v1/...` devuelve
  **`403 forbidden_access_permission`** con el token de sesión → **descartada** (esa
  licencia no incluye API; no se puede crear API token de admin).
- PERO el **backend INTERNO** que usa la propia web de Sesame **SÍ acepta la sesión** y
  permite fichar. **Contrato confirmado** (capturado del navegador, devolvió 200):

```
POST https://back-eu1.sesametime.com/api/v3/employees/{employeeId}/check-in
POST https://back-eu1.sesametime.com/api/v3/employees/{employeeId}/check-out
Content-Type: application/json

body: {
  "origin": "web",
  "coordinates": { "latitude": <float>, "longitude": <float> },
  "workCheckTypeId": null            // null = trabajo; id de pausa = pausa
}
```

- **El `{employeeId}` de la URL = a quién se ficha. El token = quién autoriza.** Por eso,
  poniendo el employeeId de Jesús, ficha en SU usuario, no en el del token.
- **Pausas (CONFIRMADO por captura del navegador, 200 OK):** son ASIMÉTRICAS.
  - **Empezar** pausa: `POST .../employees/{id}/pause` con body
    `{"origin":"web","coordinates":{…},"workCheckTypeId":null,"workBreakId":"<id>"}`.
  - **Terminar** pausa = reanudar trabajo: es un **`POST .../check-in`** normal
    (workCheckTypeId null, sin workBreakId), NO el endpoint `/pause`.
  El `workBreakId` del "Descanso" (`config.pause_check_type_id`) = `ee2a8dd8-…` (sale de
  los checks reales, no de `assigned-work-check-types`, que solo da "Teletrabajo").
- Auth en la web = cookie `USID` + `csid` + `esid`. El bot usará el **token de sesión de
  Jesús** en la cabecera (`Authorization: Bearer <token>` + `csid`), capturado de forma
  segura. **TODO Fase 2: validar que el POST se acepta por Bearer con una prueba controlada.**

---

## 3. Decisiones tomadas

- **Credenciales (opción limpia):** el bot usa el **token PROPIO de Jesús** para fichar en
  su usuario → el fichaje queda como suyo, sin marca de "tercero". (El token admin
  se queda solo en el dashboard, para LEER al equipo.)
- **Canal: Telegram** (gratis, inmediato, botones de confirmación). Plan B: WhatsApp
  Business API oficial (coste/aprobación) — solo si hiciera falta.
- **Repo independiente**, en **GitHub privado** (`github.com/jesusgascon/sesame-fichaje-bot`).
- **Casos de la máquina de estados** (ver §5): `fichar` en pausa → cerrar pausa + jornada;
  `pausar` estando fuera → preguntar e iniciar jornada ya en pausa (no inventar micro-jornada).

---

## 4. Estado actual del código (esqueleto dry-run)

Ficheros (todos en la raíz):
- **`state_machine.py`** — lógica pura fichar/pausar (estado × comando → acciones). Sin red.
  Pruébalo: `python3 state_machine.py` (imprime la tabla de decisiones).
- **`sesame_client.py`** — ejecuta acciones contra el endpoint interno. **Dry-run por
  defecto** (`DRY_RUN=True`, `ALLOW_REAL=False`); el camino real solo se ejecuta con los
  3 factores armados (`real_path_armed`), si no lanza error explicando qué falta.
  También carga `config.json`, prepara auth/coords, lee el estado real de `/checks` y
  conoce el contrato de pausas (`/pause` + `workBreakId`).
- **`telegram_bot.py`** — bot Telegram (long-polling, sin dependencias). Comandos:
  `fichar`/`/fichar`, `pausar`/`/pausar`, `/estado`, `/hoy`, `/sesion`, `/modo`,
  `/reset` (solo simulación), `/mi_chat_id`, `/vincular` (stub), `/start`, `/ayuda`.
  En dry-run usa `BOT_FAKE_STATE`; fuera
  de dry-run llama a `sesame_client.get_current_state`. Incluye caducidad de
  confirmaciones, rate-limit, lock por empleado, kill switch y auditoría JSONL con
  hashes (sin secretos ni employeeId en claro).
- **Scripts añadidos:** `run_dry_run.sh`, `run_real_state_dry_actions.sh`, `help.sh`,
  `check_config.py`, `set_telegram_commands.py`, y `probe.py` (CLI unificado de sondas
  de solo lectura: `python3 probe.py state|types|checks|pauses`; sustituye a los
  antiguos `probe_sesame_*.py`).
- **`link_store.py`** — almacén persistente (JSON `links.json`, gitignored) del vínculo
  chat↔empleado; costura para el binding cifrado por OTP de la Fase 2.
- **Tests:** `tests/` (unittest stdlib, sin red) + `run_tests.sh`. Cubren máquina de
  estados, clasificación de checks, helpers de config, `LinkStore` y el flujo del bot
  con `send` inyectado. Robustez añadida: kill switch releído en caliente desde
  `config.json`, backoff exponencial en el loop de red, errores por-update aislados.
- **Docs añadidos:** `docs/security.md` (modelo de seguridad Fase 2/D), `docs/sesame-session.md`,
  `docs/telegram-auth.md`, `docs/telegram-usage.md`, `docs/sesame-origin.md`,
  `docs/always-on.md`, `docs/production-runbook.md`, `docs/siri-shortcuts.md`,
  `docs/github-private.md`.
- **Bloque D (seguridad):** `arm_real.sh` (arma/desarma `ENABLE_REAL` con caducidad),
  `secure_perms.sh` (chmod 600). OTP de `/vincular` por consola, gate R1 (employeeId
  solo del binding en real), idempotencia (flock + `tg_offset`), auditoría que aborta
  si no puede registrar en real, logs redactados.
- **`config.example.json`** — plantilla (copiar a `config.json`, gitignored).
- **`PLAN.md`** — plan extendido (síntesis de los 3 agentes: viabilidad, arquitectura,
  seguridad). **`README.md`** — uso. **`.gitignore`** — ignora secretos/config.

Interruptores de seguridad: el modo real exige los **3 factores** (`BOT_DRY_RUN=0` +
`BOT_ALLOW_REAL=1` + `ENABLE_REAL` vigente) **y** chat vinculado por OTP; desarmado por
defecto. Detalle en `docs/security.md`.

Git: en **GitHub privado** (`origin`, rama `master`), varios commits. `config.json`,
`audit.jsonl` y `dry_state.json` están gitignored y **no** trackeados (verificado).

---

## 5. Máquina de estados (resumen; la fuente es state_machine.py)

Estados: `out` (fuera) · `working` (trabajando) · `paused` (en pausa) · `remote`
(teletrabajo, se trata como working).

| Estado | `fichar` | `pausar` |
|--------|----------|----------|
| out | CLOCK_IN | (confirmar) CLOCK_IN + PAUSE_START |
| working / remote | CLOCK_OUT (confirmar) | PAUSE_START |
| paused | PAUSE_END + CLOCK_OUT (confirmar) | PAUSE_END |

Acciones → HTTP: CLOCK_IN=check-in(workCheckTypeId null) · CLOCK_OUT=check-out(null) ·
PAUSE_START=POST `/pause` con `workBreakId` (empezar) · PAUSE_END=`check-in` normal
(terminar = reanudar trabajo).

---

## 6. Seguridad/cumplimiento — checklist mínima ANTES de cualquier escritura real

(Implementada en el Bloque D; detalle y procedimiento en `docs/security.md`.)
- [x] **R1**: en modo real el `employeeId` sale **solo** del binding verificado por OTP
      (`resolve_employee_id`), nunca de config ni del mensaje.
- [x] **Emparejamiento** chat↔empleado por **OTP por consola** (`/vincular`); binding
      persistido en `links.json` (chmod 600). Cifrado en reposo: por decisión, **permisos
      600** en vez de Fernet (cero dependencias).
- [x] **Confirmación** explícita por acción (botones Telegram), con caducidad.
- [x] **Idempotencia**: relectura de estado antes de ejecutar; lock por empleado en
      memoria + `flock`; dedupe de updates de Telegram vía `tg_offset`.
- [x] **Auditoría** append-only (chmod 600, hashes), aborta en real si no puede registrar.
      **Rate-limit** (incluye intentos de OTP). **Kill switch** releído en caliente.
- [x] Token **mínimo alcance** (tu propia sesión), nunca expuesto, logs redactados,
      ficheros a 600. Tercer factor `ENABLE_REAL` con caducidad para armar el real.
- [x] **Primera prueba real controlada HECHA (2026-06-25):** validados en real fichar
      (jornadas, "Oficina") y pausar (descansos). Modo real operativo (v1.0.0).

---

## 7. ESTADO (Fase 2 COMPLETA — v1.0.0, 2026-06-25)

Todo lo planificado de la Fase 2 está hecho y validado en real:
1. ✅ `get_state` real (`/checks` + clasificación de tramos abiertos).
2. ✅ Sesión propia + `employeeId` + `workBreakId` de pausa capturados en `config.json`.
3. ✅ Emparejamiento OTP por consola + binding persistido (`links.json`, 600).
4. ✅ Idempotencia (flock + dedupe `tg_offset`) + auditoría endurecida + kill switch en
   caliente + confirmaciones + rate-limit + logs redactados + 3er factor `ENABLE_REAL`.
5. ✅ Prueba real controlada hecha: fichar (jornadas, "Oficina") y pausar (descansos).
6. ✅ Pausas resueltas: empezar = `POST /pause` con `workBreakId`; terminar = `check-in`.

**Posibles siguientes pasos (opcionales):** selector Oficina/Remoto si mezcla
ubicaciones; endpoint HTTPS para Atajos/Siri; cifrado del binding si cambia el modelo de
amenaza. Re-armar `./arm_real.sh` cuando caduque la ventana (~30 días).

---

## 8. Cómo trabajamos aquí

- Esta carpeta = **solo el bot**. El dashboard se trabaja en su propia conversación; no lo
  toques desde aquí.
- Modo agéntico OK si Jesús lo pide (lanzar subagentes para investigar/implementar/revisar).
- Probar siempre en **dry-run**; nada real sin aprobación y sin la checklist §6.

**Arranque típico de sesión:** "Lee CLAUDE.md." El bot está en **v1.0.0**, modo real
validado. Manual de usuario en `docs/guia-completa.md`.
