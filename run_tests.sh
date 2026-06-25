#!/usr/bin/env bash
set -euo pipefail

# Tests con la stdlib (unittest), sin dependencias externas. Todo en dry-run:
# no toca red, ni Sesame, ni Telegram.
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -t . -v
