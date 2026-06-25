# Autorizacion de Telegram

El bot de Telegram tiene usuario publico. Para que nadie pueda leer tu estado de
Sesame ni disparar acciones simuladas o reales, se usa una lista local de chats
autorizados.

## Obtener tu chat_id

1. Arranca el bot.
2. En Telegram, escribe:

```text
/mi_chat_id
```

3. El bot respondera:

```text
Tu chat_id es: CHAT_ID
```

## Autorizar el chat

En `config.json`, añade ese numero:

```json
"authorized_chat_ids": [CHAT_ID]
```

Guarda el fichero y reinicia el bot.

## Vincular el chat (OTP) — necesario para fichar real

Estar autorizado da acceso; para **fichar en real** hace falta ademas vincular el
chat por OTP (asi el `employeeId` sale del binding verificado, no de config):

1. Escribe `/vincular`.
2. El bot imprime un codigo de 6 digitos en la **consola del servidor** (no en
   Telegram). Si corre como servicio:

```bash
journalctl --user -u sesame-fichaje-bot.service -f | grep VINCULACION
```

3. Escribe ese codigo en Telegram (caduca a los 300s).
4. `/modo` debe mostrar "Chat vinculado: si".

En dry-run no es obligatorio (se usa el `employee_id` de config para simular).

## Que queda publico

Aunque no estes autorizado, el bot permite:

```text
/start
/ayuda
/mi_chat_id
```

El resto de comandos (incluido `/vincular`) queda bloqueado si el `chat_id` no esta
en `authorized_chat_ids`.
