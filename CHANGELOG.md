# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/). Este proyecto
sigue versionado semántico.

## [1.0.4] — 2026-06-25

Recordatorios proactivos (backlog del segundo council). Scheduler integrado en el
loop (stdlib, sin hilos); solo lecturas y avisos, NUNCA ficha solo.

### Añadido
- **Recordatorio de salida**: si sigues fichado a tu hora de salida
  (`reminders.clock_out_time`, p.ej. 16:45), el bot te avisa con botón **SI** para
  fichar salida en un toque (pasa por el flujo normal con re-lectura y guardas). Pensado
  para cerrar a tiempo y evitar la incidencia que Sesame envía por email a salida+15.
- **Probe diario del token** (`reminders.token_probe_time`): comprueba la sesión de
  Sesame de solo lectura y avisa si caducó; también avisa si `ENABLE_REAL` está a punto
  de caducar (`enable_real_warn_days`).
- Bloque `reminders` en `config.example.json`; estado del scheduler en
  `reminders_state.json` (gitignored). Tests (`tests/test_reminders.py`); 71 en verde.

### Notas
- El recordatorio de salida NO ficha de forma autónoma: solo deja una confirmación
  pendiente; el cierre real exige tu SI (uso legítimo: presencia real).

## [1.0.3] — 2026-06-25

Pack de observabilidad y fiabilidad (segundo LLM council). Solo correcciones y
añadidos de solo lectura; el contrato con Sesame y los gates no cambian.

### Corregido
- **Doble check-in cruzando medianoche**: el estado se lee de **ayer a hoy**, no solo
  hoy. Antes, un turno abierto iniciado ayer no aparecía a las 00:01 → el bot creía que
  estabas "fuera" y un `fichar` disparaba un segundo check-in sobre un endpoint NO
  idempotente. Fix de una línea (ventana de lectura), sin tocar el camino de escritura.

### Añadido
- **Recibo read-after-write**: tras una acción real, el bot relee el estado y responde
  con la verdad (`✅ … · Ahora: trabajando`) en vez de un `✅` a ciegas.
- **Fallo de sesión en voz alta**: si el POST devuelve 401/403, avisa "tu sesión ha
  caducado: el fichaje NO se registró" en lugar de un error genérico.
- **`/salud`** (versión, modo, sesión de Sesame viva, días de `ENABLE_REAL`, kill switch)
  y **`/version`** (versión + commit). Solo lectura.
- `send()` reintenta **una vez** ante un fallo de red transitorio (solo `sendMessage`;
  el POST de fichaje nunca pasa por ahí). Evita perder el mensaje de resultado.
- Tests de regresión (`tests/test_observability_pack.py`); 64 en verde.

### Cambiado
- El trabajo remoto se etiqueta **"Remoto"** (igual que la web de Sesame), antes
  "Teletrabajo".
- `set_telegram_commands.py` registra `/salud`, `/version` y `/desvincular`.

## [1.0.2] — 2026-06-25

Fix-pack de correctitud salido de una revisión multi-perspectiva (LLM council).
Solo correcciones; el contrato con Sesame y el modelo de seguridad no cambian.

### Corregido
- **Zona horaria en `/hoy`**: las horas se convierten a `Europe/Madrid` (configurable
  con `display_timezone`). Antes, si Sesame devolvía UTC (`...Z`), se mostraban 1-2h
  desfasadas. Robusto ante DST y ante el sufijo `Z`.
- **Éxito honesto**: `run_plan` ya no muestra `✅` por ausencia de excepción; comprueba
  que cada acción fue 2xx.
- **Plan a medias**: si un plan de 2 pasos (p.ej. cerrar pausa + jornada) falla a mitad,
  el bot relee el estado real y avisa de qué se hizo y qué no, en vez de dar por bueno
  un fichaje incompleto. `execute_plan` ya no aborta con excepción: devuelve lo
  ejecutado más el fallo (sin rollback).

### Añadido
- Comando **`/desvincular`** (expone `LinkStore.remove`).
- `display_timezone` en `config.example.json`.
- Tests de regresión (`tests/test_correctness_pack.py`): zona horaria con DST, plan
  parcial, éxito honesto y omisión de la re-lectura en la ruta inmediata.

### Cambiado
- Menos latencia: en la ruta inmediata no se re-lee el estado (la re-lectura de
  idempotencia se mantiene tras una confirmación SI/NO, donde sí importa).
- Docstrings/comentarios puestos al día con la realidad (se elimina la jerga de
  "esqueleto/Fase 2/OTP contra teléfono de Sesame/cifrado en reposo"); el matiz del
  gate R1 (binding sembrado desde config) queda documentado con honestidad.

## [1.0.1] — 2026-06-25

Publicación del repositorio. Solo cambios de documentación y metadatos; **sin cambios
de funcionalidad** (el bot en producción sigue igual).

### Cambiado
- Repositorio **público** bajo licencia **MIT** (antes privado).
- `README.md` actualizado a estado de producción (v1.0.0, servicio systemd), retirada la
  redacción de fase de simulación.
- `CLAUDE.md` y docs reflejan repo público e historial purgado.

### Añadido
- `LICENSE` (MIT), `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md` y `.github/SECURITY.md`,
  alineados con el repo hermano `sesame-premium-dashboard`.

### Seguridad
- Auditoría previa a publicar: sin secretos en ficheros trackeados ni en el historial.
- **Historial reescrito** (`git filter-repo`) para purgar coordenadas GPS reales que
  estaban en `config.example.json`; sustituidas por coordenadas de ejemplo genéricas.

### Eliminado
- `docs/github-private.md` (guía de repositorio privado, obsoleta) y sus enlaces.

## [1.0.0] — 2026-06-25

Primera versión funcional: **modo real validado** (fichar y pausar de verdad en
Sesame, en tu propio usuario, desde Telegram).

### Añadido
- **Fichaje real** de jornadas: `fichar` (entrar/salir) vía `check-in`/`check-out`.
- **Pausas reales**: `pausar` (empezar/terminar descanso). Contrato confirmado del
  backend de Sesame: empezar = `POST .../pause` con `workBreakId`; terminar = `check-in`.
- **Máquina de estados** (fuera / trabajando / descansando / teletrabajando) con
  confirmaciones SI/NO y caducidad.
- **Lectura de estado real** desde `/api/v3/employees/{id}/checks` y clasificación de
  tramos abiertos. Comandos `/estado`, `/hoy`, `/sesion`, `/modo`.
- **Vinculación OTP** (`/vincular`): código por la consola del servidor (segundo factor
  fuera de banda), binding persistido en `links.json`.
- **Gate R1**: en modo real el `employeeId` sale solo del binding verificado.
- **Tercer factor `ENABLE_REAL`** con caducidad (`arm_real.sh`) para armar el modo real;
  desarmado por defecto.
- **Idempotencia**: lock por empleado (memoria + flock), relectura de estado, dedupe de
  updates de Telegram (`tg_offset`).
- **Auditoría** append-only con hashes (sin secretos); aborta la acción en real si no
  puede registrar.
- **Kill switch** releído en caliente; **rate-limit**; **logs redactados**; **permisos
  600** (`secure_perms.sh`).
- **Modos de arranque**: `run_dry_run.sh` (simulación), `run_real_state_dry_actions.sh`
  (estado real + acciones simuladas), `run_real.sh` (real).
- **Herramientas**: `probe.py` (sondas de solo lectura), `check_config.py`,
  `set_telegram_commands.py`, servicio systemd.
- **Geolocalización** Oficina/Remoto por coordenadas de `config.json`.
- **Tests** con `unittest` (stdlib, sin red): máquina de estados, clasificación,
  LinkStore, flujo del bot, gate real y contrato de endpoints.
- **Documentación**: manual completo (`docs/guia-completa.md`), seguridad
  (`docs/security.md`), runbook, sesión, autorización, uso, origen, Siri, always-on.

### Seguridad
- Cifrado en reposo por **permisos 600** (decisión: cero dependencias externas;
  máquina de un solo usuario).
- Secretos (`config.json`, `links.json`, `audit.jsonl`, `dry_state.json`) gitignored y
  nunca subidos.
