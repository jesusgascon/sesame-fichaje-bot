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

## Que queda publico

Aunque no estes autorizado, el bot permite:

```text
/start
/ayuda
/mi_chat_id
/vincular
```

El resto de comandos queda bloqueado si el `chat_id` no esta en
`authorized_chat_ids`.
