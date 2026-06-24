# Uso desde Telegram

## Como abrir la conversacion

El bot esta en:

```text
https://t.me/jesus_fichaje_bot
```

Tambien puedes buscar en Telegram:

```text
Fichajes Sesame
```

o:

```text
@jesus_fichaje_bot
```

## Primera vez

1. Abre el enlace o busca el bot.
2. Pulsa `Start` o escribe:

```text
/start
```

3. El bot mostrara la ayuda inicial.

## Comandos principales

```text
/estado
```

Muestra si estas fuera, trabajando, descansando o teletrabajando.

```text
/hoy
```

Muestra los fichajes reales de hoy.

```text
/sesion
```

Comprueba si la sesion de Sesame sigue viva.

```text
/modo
```

Muestra el modo de seguridad actual.

```text
fichar
```

Entra o sale segun el estado actual.

```text
pausar
```

Empieza o termina descanso segun el estado actual.

```text
/ayuda
```

Muestra ayuda completa.

## Confirmaciones

El bot pide `SI` o `NO` cuando la accion es delicada:

- salir de jornada
- salir estando en descanso
- pausar estando fuera

## Autorizacion

Si el bot responde:

```text
Chat no autorizado.
```

usa:

```text
/mi_chat_id
```

y añade ese valor a `authorized_chat_ids` en `config.json`.
