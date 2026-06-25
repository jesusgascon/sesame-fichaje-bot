# Plan — Bot de fichaje (Telegram → Sesame)

> ⚠️ **DOCUMENTO HISTÓRICO (síntesis inicial de los 3 agentes).** Algunas premisas
> quedaron superadas: (1) NO hay rama `feature/bot-fichaje`; todo el trabajo está en
> `master`. (2) NO existe `server.py` ni un proxy en este repo: `sesame_client.py`
> llama **directo** a `back-eu1` con tu propia sesión (ver §"Contrato CONFIRMADO").
> (3) La "API pública oficial" se **descartó** (da 403, licencia sin API). La fuente
> de verdad operativa es **`CLAUDE.md` §2–§7** y `README.md`; este PLAN se conserva
> por el registro de decisiones y el detalle de seguridad.
>
> Etapa: pasar de solo-lectura a **acciones de escritura** (fichar/pausar) sobre
> Sesame. Nada se ejecuta en real hasta validarlo por fases y con aprobación de Jesús.

## Decisiones tomadas (2026-06-24)
- **Proceder** con plan por fases en esta rama.
- **Canal: Telegram** (gratis, inmediato, botones de confirmación). Plan B: WhatsApp Business API oficial.
- **Token: probar primero el de sesión actual** (un GET a `/schedule/v1/check-types`); si no vale, API token oficial del panel admin.

## Veredicto de viabilidad (agente API)
- **SÍ es posible** vía la **API pública oficial** de Sesame (`apidocs.sesametime.com`).
- Endpoints de escritura (host `api-eu1.sesametime.com`, ya permitido por el proxy, que ya reenvía POST):
  - `POST /schedule/v1/work-entries/clock` — **toggle automático** (hace fichar/pausar nativo).
  - `POST /schedule/v1/work-entries/clock-in` · `/clock-out`.
  - `POST /schedule/v1/work-entries` — fichaje manual.
  - Pausas vía `workBreakId` (IDs desde `GET /schedule/v1/check-types` / `check-type-collections`).
- **Auth**: Bearer JWT. La app YA llama `/schedule/v1` en api-eu1 para LEER (balance, plantillas) → el token de sesión entra en esa superficie para lectura. Falta confirmar si tiene permiso de **escritura** (prueba controlada).

## Contrato CONFIRMADO (endpoint INTERNO, acepta la sesión actual)
La API oficial `/schedule/v1` da `403 forbidden_access_permission` (licencia sin API).
PERO el backend interno que usa la propia web de Sesame SÍ funciona con la sesión
(capturado del navegador, ambos devolvieron 200):
```
POST https://back-eu1.sesametime.com/api/v3/employees/{employeeId}/check-in
POST https://back-eu1.sesametime.com/api/v3/employees/{employeeId}/check-out
Content-Type: application/json
Body: { "origin":"web", "coordinates":{ "latitude":<f>, "longitude":<f> }, "workCheckTypeId": <null|pauseTypeId> }
```
- `workCheckTypeId: null` = trabajo normal. Pausas → id de tipo de pausa (de `GET /api/v3/employees/{id}/assigned-work-check-types`).
- Auth en la web = cookie USID + csid + esid. Nuestro proxy inyecta `Authorization: Bearer <token>` + csid (las lecturas `/api/v3` ya funcionan con Bearer) → **validar con prueba controlada que el POST también se acepta por Bearer**.
- Host `back-eu1` ya está en la allowlist del proxy y `do_POST` ya reenvía POST.

## Máquina de estados (4 estados: out / working / paused / remote)
| Estado | `fichar` | `pausar` |
|---|---|---|
| out (fuera) | CLOCK_IN | **P2 (recomendado):** preguntar e iniciar jornada ya en pausa |
| working | CLOCK_OUT | PAUSE_START |
| remote (teletrabajo) | CLOCK_OUT | PAUSE_START |
| paused | **F1 (recomendado):** PAUSE_END + CLOCK_OUT | PAUSE_END (volver a trabajar) |

Decisiones a confirmar: **F** (fichar en pausa) y **P** (pausar fuera). Nota: el endpoint `/clock`
de Sesame puede simplificar el toggle.

## Seguridad / cumplimiento — innegociables antes de escribir
- **R1 (crítico):** el proxy reenvía POST autenticado **sin** pedir contraseña si hay token →
  cerrar el gate: binding/sesión obligatorio en TODA ruta de escritura.
- **Emparejamiento verificado** chat↔empleado (OTP fuera de banda); `employeeId` derivado del
  binding, **nunca** del mensaje. Cada uno solo actúa sobre su propio empleado.
- **Dry-run por defecto**, **confirmación** por acción, **idempotencia** (no duplicar/solapar),
  **kill switch**, **auditoría** append-only, **rate-limit**.
- **Uso legítimo = reflejar la jornada REAL.** No automatizar sin presencia, no fichar a terceros,
  no enmascarar el origen. Conviene autorización de empresa + base RGPD para el binding.

## Plan por fases
1. **Fase 1 — Viabilidad + andamiaje (SIN escrituras):** rama creada ✅; probe del token
   (GET check-types desde la consola del navegador); esqueleto bot Telegram (eco) + endpoints
   en dry-run. *[en curso]*
2. **Fase 2 — Lógica + seguridad:** máquina de estados, emparejamiento OTP, fix R1, idempotencia,
   auditoría, kill switch — todo en dry-run (simula, no escribe).
3. **Fase 3 — Primera escritura REAL controlada:** Jesús fichándose a sí mismo, con confirmación.
   Validar y ampliar.

## Arquitectura
```
Empleado → Bot (Telegram, adapter + state machine + link store)
         → server.py (NUEVOS endpoints /bot/* de escritura, gate + cifrado Fernet)
         → Sesame (api-eu1 /schedule/v1)
```
El bot nunca ve el Bearer; el proxy lo inyecta. Auth servicio↔proxy con secreto dedicado.
