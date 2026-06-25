# Guía completa — sesame-fichaje-bot

Manual de referencia del bot de Telegram para fichar y pausar en Sesame desde el
móvil, en tu propio usuario. Para consultar cualquier cosa: comandos, puesta en
marcha, pausas, modos, herramientas y resolución de problemas.

> Uso legítimo: el bot refleja **tu jornada real** en **tu** usuario, igual que la
> app oficial de Sesame. No sirve para fichar a terceros ni para automatizar sin
> presencia real.

---

## 1. Qué es y cómo funciona

Escribes `fichar` o `pausar` al bot de Telegram y este registra la acción en Sesame,
en tu usuario. Por dentro:

- **Telegram** recibe tu mensaje y el bot decide qué hacer según tu estado actual.
- El bot lee tu **estado real** en Sesame y, si la acción procede, hace la llamada
  al backend interno de Sesame con **tu propia sesión** (la misma que usa la web).
- El fichaje queda registrado como tuyo, con `origin: web`.

El bot **no usa el GPS del móvil**: manda las **coordenadas fijas** de `config.json`
(ver §8, Oficina vs Remoto).

Lógica tipo interruptor (toggle): `fichar` alterna entrar/salir; `pausar` alterna
empezar/terminar descanso. La tabla completa está en §4.

---

## 2. Puesta en marcha

### 2.1 Configuración (`config.json`)

Copia la plantilla y rellénala (queda gitignored, nunca se sube):

```bash
cp config.example.json config.json
```

Campos:

- `telegram_token`: token del bot, de `@BotFather`.
- `authorized_chat_ids`: lista con tu chat_id (lo obtienes con `/mi_chat_id`).
- Sesión de Sesame: `usid` (cookie USID) **o** `sesame_token` (Bearer), más `csid`,
  `esid` y `employee_id`. Cómo sacarlos: `docs/sesame-session.md`.
- `coordinates`: latitud/longitud de tu sitio de trabajo (ver §8).
- `pause_check_type_id`: el **workBreakId** de tu "Descanso" (ver §5).
- `kill_switch`: `true`/`false` (freno de emergencia, §7).

Comprueba sin imprimir secretos:

```bash
python3 check_config.py
```

### 2.2 Registrar los comandos en el menú de Telegram

```bash
python3 set_telegram_commands.py
```

### 2.3 Autorizar tu chat

Arranca el bot (en simulación, §6), escribe `/mi_chat_id`, y añade ese número a
`authorized_chat_ids` en `config.json`. Reinicia el bot.

### 2.4 Vincular tu chat (necesario para fichar real)

Estar autorizado da acceso; para **fichar real** hay que vincular el chat por OTP,
así el `employeeId` sale del vínculo verificado y no de la config:

1. Escribe `/vincular`.
2. El bot imprime un código de 6 dígitos en la **consola del servidor** (no en
   Telegram). Si corre como servicio:
   `journalctl --user -u sesame-fichaje-bot.service -f | grep VINCULACION`
3. Escribe el código en Telegram (caduca a los 300s).
4. `/modo` debe mostrar "Chat vinculado: sí".

---

## 3. Comandos de Telegram

Puedes usarlos con `/` (menú) o sin barra donde se indica.

| Comando | Qué hace |
|---|---|
| `/start` | Mensaje de bienvenida y modo actual. |
| `/ayuda` | Ayuda resumida dentro de Telegram. |
| `/estado` | Tu estado: **fuera**, **trabajando**, **descansando** o **teletrabajando**. |
| `/hoy` | Lista tus fichajes de hoy (solo en modo con lectura real). |
| `/fichar` o `fichar` | Entra o sale, según tu estado (toggle). Pide SI/NO al salir. |
| `/pausar` o `pausar` | Empieza o termina el descanso (toggle). |
| `/sesion` | Comprueba si tu sesión de Sesame sigue viva. |
| `/modo` | Modo de seguridad: autorizado, vinculado, lee real, ficha real, armado, kill switch. |
| `/vincular` | Vincula este chat con tu usuario por OTP (código por consola). |
| `/desvincular` | Desvincula este chat de tu usuario. |
| `/mi_chat_id` | Muestra tu chat_id para autorizarte. |
| `/reset` | Reinicia el estado simulado a "fuera" (solo en simulación). |
| `SI` / `NO` | Confirma o cancela una acción delicada. |

### Confirmaciones

El bot pide `SI`/`NO` (con caducidad de 120s) en acciones delicadas:

- Salir de jornada (`fichar` estando trabajando).
- `fichar` estando en pausa (cierra la pausa y la jornada).
- `pausar` estando fuera (abre jornada y entra en pausa).

---

## 4. Máquina de estados (qué hace cada acción)

Estados: **fuera** (out) · **trabajando** (working) · **descansando** (paused) ·
**teletrabajando** (remote, se trata como trabajando).

| Estado | `fichar` | `pausar` |
|--------|----------|----------|
| fuera | Inicia jornada | (confirmar) Inicia jornada y entra en pausa |
| trabajando / teletrabajando | (confirmar) Finaliza jornada | Empieza descanso |
| descansando | (confirmar) Cierra pausa y finaliza jornada | Termina descanso, vuelve al trabajo |

Importante: **terminar una pausa NO cierra la jornada** — vuelves a trabajar en la
misma jornada (el descanso es un tramo dentro del día). No tienes que volver a
`fichar` tras una pausa.

---

## 5. Cómo funcionan las pausas

Las pausas en Sesame no son un check-in/out normal:

- **Empezar pausa:** `POST .../employees/{id}/pause` con `workBreakId` (el id del tipo
  "Descanso") y `workCheckTypeId: null`.
- **Terminar pausa:** es un **`check-in` normal** (reanudar trabajo), no el endpoint
  `/pause`.

El `workBreakId` del "Descanso" se pone en `config.json` → `pause_check_type_id`. Para
encontrarlo, mira tus fichajes reales:

```bash
BOT_DRY_RUN=0 python3 probe.py pauses
```

Saldrá algo como `Descanso: ee2a8dd8-...`. Ese id es el que va en `pause_check_type_id`.

> Nota: `assigned-work-check-types` devuelve "Teletrabajo", que **no** es la pausa. El
> id de la pausa sale de los checks reales (campo `workBreakId`), no de ahí.

---

## 6. Modos de funcionamiento

El bot tiene tres modos, de menos a más capacidad:

### Simulación pura — `./run_dry_run.sh`
Ni lee ni escribe en Sesame. `/estado` usa un estado falso (`BOT_FAKE_STATE`). Sirve
para probar Telegram y la lógica sin ningún riesgo.

### Estado real + acciones simuladas — `./run_real_state_dry_actions.sh`
`/estado`, `/hoy` y `/sesion` leen Sesame **real**; `fichar`/`pausar` siguen
**simulados**. Modo seguro de preproducción.

### Real — `./run_real.sh`
Puede crear fichajes reales. Aun así, **no ficha** salvo que se den **todos** estos
factores (ver §7):

1. `BOT_DRY_RUN=0` y `BOT_ALLOW_REAL=1` (los pone `run_real.sh`).
2. Fichero `ENABLE_REAL` vigente (`./arm_real.sh`).
3. Chat vinculado por OTP.
4. Confirmación SI en las acciones delicadas.

Comprueba en qué modo estás con `/modo`.

---

## 7. Seguridad (resumen)

Detalle completo en `docs/security.md`. Lo esencial:

- **Tres factores** para armar el modo real (arriba). Desarmado por defecto.
- **Vinculación OTP** por consola; el `employeeId` sale del vínculo, nunca de la config
  (gate R1). El vínculo se guarda en `links.json` (permisos 600).
- **Idempotencia:** lock por empleado (memoria + flock), relectura de estado antes de
  ejecutar, y dedupe de mensajes de Telegram (`tg_offset`).
- **Auditoría** append-only (`audit.jsonl`, permisos 600, con hashes; en real aborta la
  acción si no puede registrarla).
- **Kill switch:** `"kill_switch": true` en `config.json` (se relee en caliente).
- **Permisos 600** en ficheros sensibles: `./secure_perms.sh`. Sin cifrado por decisión
  (máquina de un solo usuario, cero dependencias).
- **Logs redactados** (sin coordenadas, employeeId ni body de error).

### Armar / desarmar el modo real

```bash
./arm_real.sh        # arma el 3er factor (ventana de 35 días por defecto)
./arm_real.sh off    # desarma
```

### Frenos de emergencia

- `"kill_switch": true` en `config.json` (efecto inmediato).
- `./arm_real.sh off` (desarma el real).
- `systemctl --user stop sesame-fichaje-bot.service` (para el bot).

---

## 8. Geolocalización: Oficina vs Remoto

Sesame marca **Oficina** o **Remoto** según si las coordenadas caen dentro de la zona
de tu oficina. El bot **siempre** manda las coordenadas de `config.json` (no el GPS del
móvil), así que:

- Coordenadas de la oficina → fichajes como **Oficina**.
- Otras coordenadas → **Remoto**.

Para usar las de tu oficina, mira las de tus fichajes "Oficina" reales y ponlas en
`config.json` → `coordinates`. Si mezclas oficina y teletrabajo, las coordenadas fijas
no lo distinguen solas; en ese caso, díselo al mantenedor para añadir un selector.

---

## 9. Herramientas y scripts

| Comando | Para qué |
|---|---|
| `./help.sh` | Chuleta rápida de todo. |
| `./run_dry_run.sh` | Arranca en simulación pura. |
| `./run_real_state_dry_actions.sh` | Estado real, acciones simuladas. |
| `./run_real.sh` | Arranca en modo real. |
| `./arm_real.sh` / `./arm_real.sh off` | Arma/desarma el 3er factor (`ENABLE_REAL`). |
| `./secure_perms.sh` | Permisos 600 en config y ficheros de estado. |
| `./run_tests.sh` | Suite de tests (unittest, sin red). |
| `python3 check_config.py` | Revisa la config sin imprimir secretos. |
| `python3 set_telegram_commands.py` | Registra los comandos en el menú de Telegram. |
| `python3 probe.py state` | Estado real actual (solo lectura). |
| `python3 probe.py types` | Tipos de pausa/asistencia asignados. |
| `python3 probe.py checks` | Vuelca los checks de hoy (claves seguras). |
| `python3 probe.py pauses` | Busca el id de "Descanso" en los checks. |

Las sondas `probe.py` leen Sesame real si usas `BOT_DRY_RUN=0`, p. ej.
`BOT_DRY_RUN=0 python3 probe.py state`.

---

## 10. Dejarlo siempre encendido (servicio)

Para fichar desde el móvil sin tener el ordenador delante:

```bash
cp deploy/sesame-fichaje-bot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now sesame-fichaje-bot.service
loginctl enable-linger "$USER"   # que arranque sin sesión abierta
```

Operación:

```bash
systemctl --user status  sesame-fichaje-bot.service   # estado
journalctl --user -u sesame-fichaje-bot.service -f    # logs
systemctl --user restart sesame-fichaje-bot.service   # tras cambiar config.json
systemctl --user stop    sesame-fichaje-bot.service   # parar
```

El servicio arranca en modo real; el binding (`links.json`) y `ENABLE_REAL` persisten,
así que no hay que revincular ni rearmar en cada arranque. Recuerda **rearmar
`./arm_real.sh`** cuando caduque la ventana (35 días).

---

## 11. Resolución de problemas

| Síntoma | Causa probable / solución |
|---|---|
| "Chat no autorizado" | Tu chat_id no está en `authorized_chat_ids`. Usa `/mi_chat_id` y añádelo. |
| "No estás vinculado. Usa /vincular" | En modo real falta el binding OTP. Haz `/vincular`. |
| `/sesion` dice "no conectada" | Sesión de Sesame caducada. Renueva `usid`/`csid`/`esid` (`docs/sesame-session.md`) y reinicia. |
| "Camino REAL no armado: falta ENABLE_REAL" | Ejecuta `./arm_real.sh`. |
| "Camino REAL no armado: ENABLE_REAL caducado" | Vuelve a `./arm_real.sh` (la ventana caduca a 35 días). |
| HTTP 422 al fichar/pausar | Body o endpoint incorrecto para tu Sesame. Captura la petición real del navegador y ajústalo (ver §5). |
| Sale "Remoto" y querías "Oficina" | Coordenadas de `config.json` fuera de la oficina (§8). |
| "Acciones bloqueadas por kill switch" | `kill_switch` está en `true` en `config.json`. Ponlo en `false`. |
| Cambié `config.json` y no surte efecto | Las coordenadas y el kill switch se releen en caliente; el resto (token, sesión, chats) requiere reiniciar el bot. |

---

## 12. Privacidad y cumplimiento

- El bot usa **tu propia sesión** y ficha en **tu** usuario.
- No oculta el origen: declara `origin: web` (es el flujo web interno de Sesame).
- Refleja tu jornada real. No fichar a terceros, no automatizar sin presencia.
- Secretos (`config.json`, `links.json`, `audit.jsonl`, `dry_state.json`) están
  gitignored y a permisos 600; nunca se suben al repositorio.

---

## 13. Más documentación

- `docs/security.md` — modelo de seguridad detallado y checklist de prueba real.
- `docs/production-runbook.md` — operar el bot, servicio, logs, prueba real.
- `docs/sesame-session.md` — obtener y renovar la sesión de Sesame.
- `docs/telegram-auth.md` — autorización y vinculación OTP.
- `docs/telegram-usage.md` — abrir y usar el bot en Telegram.
- `docs/sesame-origin.md` — cómo se ve el origen del fichaje en Sesame.
- `docs/siri-shortcuts.md` — Atajos/Siri en iPhone.
- `docs/always-on.md` — servicio systemd siempre encendido.
