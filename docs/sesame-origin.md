# Como se vera el fichaje en Sesame

El endpoint interno confirmado recibe este cuerpo:

```json
{
  "origin": "web",
  "coordinates": {
    "latitude": 40.4168,
    "longitude": -3.7038
  },
  "workCheckTypeId": null
}
```

Por tanto, cuando se habilite el modo real, el origen que enviara el bot sera:

```text
web
```

## Que significa

No aparecera como Telegram, WhatsApp, tablet o app movil, porque Sesame no recibe
esos valores desde este bot. El bot llama al mismo backend web interno y declara
`origin: "web"`.

En la interfaz de Sesame lo esperable es que se vea como fichaje web o equivalente.
La etiqueta exacta depende de como Sesame traduzca internamente `origin=web` en su
UI. Esto se validara en la prueba real controlada.

## Coordenadas

El bot manda las coordenadas de `config.json`:

```json
"coordinates": {
  "latitude": 40.4168,
  "longitude": -3.7038
}
```

Antes de produccion real hay que confirmar que esas coordenadas son correctas y
aceptables para el uso previsto.

## Importante

El bot no debe intentar ocultar el origen ni fingir ser app movil. La configuracion
actual refleja que la accion sale del flujo web interno de Sesame.
