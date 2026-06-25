# Guía de contribución

Gracias por tu interés en **sesame-fichaje-bot**. Es un bot de **Telegram** que **escribe**
en Sesame HR (ficha jornadas y pausas) para un **único usuario: el dueño de la sesión**.
Por su naturaleza (escribe en un sistema real), la seguridad y el uso legítimo son lo primero.

## Principios

- **Sin dependencias externas**: solo Python 3 de la librería estándar (long-polling, JSON,
  `urllib`). No añadas paquetes salvo justificación fuerte.
- **Seguro por defecto**: el camino real está **desarmado** y exige 3 factores simultáneos
  (`BOT_DRY_RUN=0` + `BOT_ALLOW_REAL=1` + fichero `ENABLE_REAL` vigente) **y** un chat
  vinculado por OTP. Ningún cambio debe debilitar estas guardas.
- **Uso legítimo únicamente**: el bot refleja **tu propia jornada real**, igual que la app
  oficial de Sesame. Prohibido fichar a terceros, automatizar sin presencia real o enmascarar
  el origen del fichaje.
- **Nunca subir secretos**: `config.json`, `links.json`, `audit.jsonl`, `ENABLE_REAL` y demás
  están en `.gitignore`. No los trackees ni pegues tokens en código, tests ni docs.
- Ver también [`CLAUDE.md`](./CLAUDE.md), [`PLAN.md`](./PLAN.md) y [`docs/security.md`](./docs/security.md)
  para el contexto y el modelo de seguridad detallado.

## Puesta en marcha (simulación, sin red)

```bash
cp config.example.json config.json   # rellena tus valores (gitignored)
./run_tests.sh                        # suite unittest (stdlib), todo en dry-run
./run_dry_run.sh                      # arranca el bot en modo simulación
```

## Estilo de código

- **Python**: PEP 8, funciones pequeñas y nombres descriptivos.
- Comentarios en español (inglés admitido para lógica compleja), coherentes con el código existente.
- Mantén la lógica pura (máquina de estados) separada de la red (`sesame_client.py`).

## Mensajes de commit

Formato: `tipo: descripción` — tipos: `feat`, `fix`, `refactor`, `docs`, `perf`, `security`, `test`.

```
feat: selector Oficina/Remoto al fichar entrada
fix: relectura de estado antes de ejecutar para evitar acciones antiguas
docs: alinear README con el estado de producción
```

## Antes de abrir un PR

```bash
python3 -m py_compile *.py            # compila sin errores
./run_tests.sh                        # toda la suite en verde
# Revisa que el diff no contenga secretos:
git diff | grep -iE "token|bearer|usid|csid|password|key" | grep -vE "example|gitignore|_comment"
```

- Prueba **siempre en dry-run**. Nada en modo real sin aprobación del responsable y sin la
  checklist de [`docs/security.md`](./docs/security.md).
- Actualiza `README.md` / `CHANGELOG.md` / docs si cambia el comportamiento.

## Licencia

Al contribuir, aceptas que tu código se publique bajo la licencia **MIT** (ver [`LICENSE`](./LICENSE)).
