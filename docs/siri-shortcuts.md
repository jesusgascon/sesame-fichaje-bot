# Siri y Atajos de iPhone

El bot soporta comandos slash preparados para Atajos:

```text
/fichar
/pausar
/hoy
/estado
/sesion
/modo
```

## Registrar comandos en Telegram

Desde el proyecto:

```bash
python3 set_telegram_commands.py
```

Esto hace que Telegram muestre los comandos en el menu del bot.

## Atajo basico: abrir el bot

1. Abre `Atajos` en iPhone.
2. Pulsa `+`.
3. Añade accion `Abrir URL`.
4. URL:

```text
https://t.me/jesus_fichaje_bot
```

5. Nombre del atajo:

```text
Fichajes Sesame
```

Uso:

```text
Oye Siri, Fichajes Sesame
```

Siri abre el chat. Luego puedes tocar/escribir:

```text
/fichar
/pausar
/hoy
```

## Atajos por accion

Puedes crear atajos separados:

- `Fichar Sesame`
- `Pausa Sesame`
- `Fichajes de hoy`

Todos pueden abrir la misma URL del bot:

```text
https://t.me/jesus_fichaje_bot
```

La ventaja es que Siri te lleva directo al chat con la intencion clara. Telegram no
permite de forma fiable que un enlace envie automaticamente un mensaje al bot como
si fueras tu sin confirmacion del usuario.

## Automatizacion completa

Para que `Oye Siri, fichar Sesame` fiche sin abrir Telegram ni tocar nada, hace
falta otro paso tecnico:

1. Crear un endpoint HTTPS privado.
2. Protegerlo con token secreto.
3. Hacer que Atajos llame a ese endpoint.
4. El endpoint ejecutaria la misma logica del bot.

Eso requiere mas seguridad que Telegram:

- HTTPS
- token secreto por atajo
- rate-limit
- auditoria
- confirmacion o bloqueo de acciones peligrosas

Por ahora, el camino recomendado es usar Siri para abrir el bot y ejecutar los
comandos slash desde Telegram. Cuando el fichaje real este validado, se puede
construir el endpoint de Atajos si sigue mereciendo la pena.
