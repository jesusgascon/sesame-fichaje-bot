# Política de Seguridad

## Reportar una vulnerabilidad

**No abras un issue público** para vulnerabilidades de seguridad. En su lugar:

1. Usa el aviso de seguridad privado de GitHub: **Security → Report a vulnerability**
   (https://github.com/jesusgascon/sesame-fichaje-bot/security/advisories/new), o
2. Escribe a **jesusgascon@gmail.com** con el asunto
   `[SECURITY] sesame-fichaje-bot`.

Incluye una descripción, los pasos para reproducir (sin exponer tokens o credenciales reales),
el impacto estimado y, si la tienes, una propuesta de solución. Se acusará recibo en un plazo
razonable y se comunicará una estimación de corrección.

## Ámbito

Cubierto por esta política:
- Fuga de tokens de sesión de Sesame, tokens de Telegram, cookies (`USID`/`csid`/`esid`),
  `employeeId`, teléfono u otros datos personales en código, logs o auditoría.
- Bypass de los **3 factores** que arman el modo real (`BOT_DRY_RUN`, `BOT_ALLOW_REAL`,
  `ENABLE_REAL`) o del vínculo chat↔empleado por OTP.
- Bypass del gate R1 (el `employeeId` en real debe salir solo del binding verificado).
- Fallos de idempotencia (doble fichaje), del kill switch o del rate-limit.
- Cualquier vía que permita fichar a un tercero o sin presencia real (uso ilegítimo).

Fuera de ámbito:
- Vulnerabilidades de la propia API/backend de Sesame HR.
- Ataques que requieran acceso físico o root en la máquina que ejecuta el bot.
- Ingeniería social para obtener credenciales.

## Buenas prácticas para usuarios

1. **Nunca** subas tokens, cookies o `config.json` reales al repositorio (están en `.gitignore`).
2. Aplica permisos restrictivos con `./secure_perms.sh` (ficheros sensibles a `600`).
3. Mantén el modo real **desarmado** salvo cuando lo uses; rearma `ENABLE_REAL` con caducidad
   vía `./arm_real.sh`.
4. Renueva tu sesión de Sesame periódicamente (ver `docs/sesame-session.md`).
5. Revisa la auditoría (`audit.jsonl`) ante cualquier acción inesperada.
