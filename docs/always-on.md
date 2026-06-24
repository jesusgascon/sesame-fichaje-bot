# Dejar el bot siempre encendido

Ahora mismo el bot corre mientras la terminal esta abierta. Para dejarlo siempre
ejecutando en Linux se puede usar un servicio de usuario de systemd.

El servicio preparado arranca en este modo:

```text
estado real de Sesame + acciones simuladas
```

Es decir:

- `/estado`, `/hoy` y `/sesion` leen Sesame real.
- `fichar` y `pausar` siguen sin escribir en Sesame porque `BOT_ALLOW_REAL=0`.

## Instalar servicio

Desde la carpeta del proyecto:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/sesame-fichaje-bot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable sesame-fichaje-bot.service
systemctl --user start sesame-fichaje-bot.service
```

## Ver estado

```bash
systemctl --user status sesame-fichaje-bot.service
```

## Ver logs

```bash
journalctl --user -u sesame-fichaje-bot.service -f
```

## Parar

```bash
systemctl --user stop sesame-fichaje-bot.service
```

## Reiniciar tras cambiar config.json

```bash
systemctl --user restart sesame-fichaje-bot.service
```

## Arrancar aunque no haya terminal abierta

Para que el servicio de usuario pueda arrancar al iniciar sesion y mantenerse sin
una terminal abierta:

```bash
loginctl enable-linger "$USER"
```

Esto puede requerir permisos del sistema.
