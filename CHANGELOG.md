# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/). Este proyecto
sigue versionado semántico.

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
