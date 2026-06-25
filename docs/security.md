# Modelo de seguridad (Fase 2 / Bloque D)

Resumen de las guardas que protegen tus credenciales y evitan fichajes
accidentales o erróneos. Uso legítimo: reflejar TU jornada real en TU usuario.

## Decisiones de diseño

- **Vinculación:** OTP por consola del servidor (no SMS).
- **Cifrado en reposo:** ninguno; protección por **permisos `600`** + máquina de un
  solo usuario. Mantiene el principio de "cero dependencias externas".
- **Activar el camino real:** tercer factor por **fichero `ENABLE_REAL` con caducidad**.

## Camino real: tres factores (desarmado por defecto)

Para que el bot ejecute un POST real en Sesame deben darse **a la vez**:

1. `BOT_DRY_RUN=0`
2. `BOT_ALLOW_REAL=1`
3. Fichero `ENABLE_REAL` presente y **no caducado** (`BOT_ENABLE_REAL_TTL_SECONDS`,
   por defecto 3600s). Se crea con `./arm_real.sh` y se borra con `./arm_real.sh off`.

Y además, en el flujo:

4. El chat debe estar **vinculado por OTP** (el `employeeId` sale del binding, nunca
   de config ni del mensaje — *gate R1*).
5. Confirmación SI/NO vigente para las acciones delicadas.

Si falta cualquiera, el camino real **no se arma** y `execute_action` lanza un error
explicando qué falta. Por defecto (sin `ENABLE_REAL`) el bot nunca ficha real.

Comprueba el estado desde Telegram con `/modo` (muestra "Camino real armado" y "Chat
vinculado").

## Vinculación por OTP (`/vincular`)

1. Un chat **autorizado** (`authorized_chat_ids`) escribe `/vincular`.
2. El bot genera un código de 6 dígitos y lo **imprime en la consola/journald del
   servidor** (solo lo ve quien opera la máquina; ese es el segundo factor fuera de
   banda). En Telegram NO se muestra el código.
3. El usuario escribe el código en Telegram. Si coincide y no ha caducado
   (`BOT_OTP_TTL_SECONDS`, 300s), se persiste el binding `chat -> employeeId` en
   `links.json` (permisos 600).
4. A partir de ahí, en modo real el `employeeId` se deriva solo de ese binding.

Ver el código en los logs del servicio:

```bash
journalctl --user -u sesame-fichaje-bot.service -f | grep VINCULACION
```

## Idempotencia

- **Lock por empleado**: en memoria + `flock` de fichero (`.locks/`), de modo que dos
  instancias o un reinicio no provoquen acciones solapadas.
- **Relectura de estado** justo antes de ejecutar: si el estado cambió, no se ejecuta
  una acción antigua.
- **Dedupe de updates de Telegram**: el `offset` se persiste (`tg_offset`) y se marca
  el mensaje como procesado **antes** de actuar, así un crash pierde el mensaje
  (reintentable) en vez de duplicar un fichaje.

## Auditoría

- JSONL append-only (`audit.jsonl`), permisos 600. `chat`/`employee` se guardan como
  `sha256[:16]`, nunca en claro; sin tokens ni coordenadas.
- En modo real, si no se puede registrar el intento, la acción **se aborta** (un
  fichaje sin auditar es peor que no fichar).

## Secretos y logs

- `config.json`, `links.json`, `audit.jsonl`, `dry_state.json` → `600`. Lánzalo con
  `./secure_perms.sh`. Todos están gitignored.
- Logs **redactados**: en dry-run no se imprime URL completa, employeeId ni
  coordenadas; los errores de Sesame no vuelcan el body crudo (posible PII).
- El OTP se imprime en consola a propósito (segundo factor), pero **no** se audita ni
  se manda por Telegram.

## Kill switch

- `"kill_switch": true` en `config.json` se **relee en caliente** (sin reiniciar).
- Mecanismo de parada definitivo: `systemctl --user stop sesame-fichaje-bot.service`.

## Checklist antes de la PRIMERA prueba real (con OK explícito de Jesús)

1. `./secure_perms.sh` (permisos 600).
2. `/sesion` en verde (usid/csid/esid vivos).
3. `/vincular` + código de consola → `/modo` muestra "Chat vinculado: sí".
4. Confirmar que estás realmente fuera de jornada.
5. `BOT_DRY_RUN=0 BOT_ALLOW_REAL=1` y `./arm_real.sh` (ventana corta).
6. `fichar` → confirmar → ver el fichaje en Sesame → `fichar` para cerrar → `/hoy`.
7. `./arm_real.sh off` al terminar.
