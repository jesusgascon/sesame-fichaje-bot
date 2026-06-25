#!/usr/bin/env bash
set -euo pipefail

# Permisos 600 (solo el dueño) en los ficheros con datos sensibles.
# Política del proyecto: cero dependencias de cifrado; la protección en reposo
# es chmod 600 + que la máquina sea de un solo usuario (ver docs/security.md).
cd "$(dirname "$0")"

for f in config.json links.json audit.jsonl dry_state.json; do
  if [[ -f "$f" ]]; then
    chmod 600 "$f"
    echo "600  $f"
  fi
done

echo "Permisos asegurados."
