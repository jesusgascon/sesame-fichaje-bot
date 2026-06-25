# Como se vera el fichaje en Sesame

El endpoint interno confirmado recibe este cuerpo:

```json
{
  "origin": "web",
  "coordinates": {
    "latitude": 41.6312893,
    "longitude": -0.9101856
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

**Validado en real:** los fichajes del bot aparecen en Sesame como **Oficina** o
**Remoto** segun las coordenadas (ver abajo), igual que la app oficial. No aparece
ninguna marca de bot ni de Telegram.

## Coordenadas: Oficina vs Remoto

Sesame decide **Oficina** o **Remoto** segun si las coordenadas caen dentro de la zona
de tu oficina. El bot **no usa el GPS del movil**: siempre manda las coordenadas fijas
de `config.json`:

```json
"coordinates": {
  "latitude": 41.6312893,
  "longitude": -0.9101856
}
```

- Coordenadas dentro de la oficina -> fichajes como **Oficina**.
- Otras coordenadas -> **Remoto**.

Para que salga "Oficina", pon las coordenadas de tu oficina (puedes leerlas de tus
fichajes "Oficina" reales). Si mezclas oficina y teletrabajo, las coordenadas fijas no
lo distinguen solas. Ver `docs/guia-completa.md` §8.

## Importante

El bot no debe intentar ocultar el origen ni fingir ser app movil. La configuracion
actual refleja que la accion sale del flujo web interno de Sesame.
