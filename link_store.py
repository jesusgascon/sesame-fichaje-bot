"""Almacén persistente del vínculo chat <-> empleado (Telegram <-> Sesame).

JSON plano gitignored (`links.json`, chmod 600). `set()` persiste el binding que
crea `/vincular` al verificar el OTP, de modo que sobrevive a reinicios (a
diferencia de un dict en memoria). Cifrado en reposo descartado por decisión (cero
dependencias): se protege con permisos 600 sobre el fichero.
"""

import json
import os
from pathlib import Path


class LinkStore:
    def __init__(self, path):
        self.path = Path(path)
        self._data = {}
        self.load()

    def load(self):
        if not self.path.exists():
            self._data = {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, OSError, ValueError):
            self._data = {}

    def save(self):
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        # El binding es sensible: solo el dueño puede leerlo.
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def get(self, chat_id):
        return self._data.get(str(chat_id))

    def set(self, chat_id, employee_id):
        self._data[str(chat_id)] = str(employee_id)
        self.save()

    def remove(self, chat_id):
        if str(chat_id) in self._data:
            del self._data[str(chat_id)]
            self.save()

    def all(self):
        return dict(self._data)
