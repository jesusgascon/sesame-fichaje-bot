# Sesion de Sesame

El bot usa tu sesion propia de Sesame para leer estado y, mas adelante, fichar en
tu usuario. Estos valores son secretos. No los pegues en chats ni commits.

## Que valores hacen falta

En `config.json`:

```json
"sesame_token": "",
"usid": "",
"csid": "",
"esid": "",
"employee_id": ""
```

Normalmente usamos `usid` + `csid` + `esid` + `employee_id`. Deja
`sesame_token` vacio si no ves una cabecera `Authorization: Bearer ...`.

## Como obtenerlos

1. Entra en Sesame desde Chrome o Edge.
2. Abre herramientas de desarrollador con `F12`.
3. Ve a `Network` / `Red`.
4. Activa el filtro `Fetch/XHR`.
5. Recarga Sesame con `Ctrl+R`.
6. Abre una peticion a `back-eu1.sesametime.com`, por ejemplo:

```text
/api/v3/employees/.../checks?from=...&to=...&includeOut=true
```

## employee_id

En la URL:

```text
/api/v3/employees/xxxxxxxx/checks
```

`employee_id` es lo que va entre `/employees/` y `/checks`.

## csid

En la misma peticion:

1. Abre `Headers` / `Cabeceras`.
2. Baja a `Request Headers`.
3. Copia el valor de la cabecera `csid`.

## esid

En `Request Headers`, copia el valor de la cabecera `esid`.

Normalmente coincide con `employee_id`.

## usid

En `Request Headers`, busca la cabecera `cookie`.

Dentro de la linea larga, busca:

```text
USID=
```

Copia solo lo que va despues de `USID=` y antes del siguiente `;`.

Ejemplo:

```text
cookie: a=1; USID=VALOR_LARGO; otra=2
```

En `config.json` pega solo:

```json
"usid": "VALOR_LARGO"
```

## Si hay Authorization

Si alguna peticion muestra:

```text
Authorization: Bearer TOKEN_LARGO
```

puedes pegar solo lo que va despues de `Bearer ` en:

```json
"sesame_token": "TOKEN_LARGO"
```

Si no aparece, deja `sesame_token` vacio y usa `usid`.

## Comprobar que funciona

Sin imprimir secretos:

```bash
python3 check_config.py
python3 probe_sesame_state.py
python3 probe_sesame_readonly.py
```

Desde Telegram:

```text
/sesion
/estado
/hoy
```

## Cuando caduque

Si el bot responde que la sesion de Sesame no esta conectada:

1. Cierra sesion en Sesame.
2. Vuelve a entrar.
3. Repite los pasos para obtener `usid`, `csid` y `esid`.
4. Actualiza `config.json`.
5. Reinicia el bot.

No envies estos valores por Telegram ni por el chat del proyecto.
