"""État persistant du kit, lu par Home Assistant via GET /status."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import STATE

_LOCK = threading.Lock()
_PATH = STATE / "status.json"

DEFAULT = {
    "derniere_generation": None,      # ISO 8601
    "version_nas": None,              # empreinte globale du kit généré
    "version_kindle": None,           # empreinte lue sur le Kindle après livraison
    "derniere_livraison": None,       # ISO 8601 de la dernière livraison vérifiée
    "a_jour": False,                  # version_nas == version_kindle
    "version_papier": None,           # empreinte du PDF à imprimer
    "version_papier_imprimee": None,  # empreinte au dernier « imprimé » confirmé
    "papier_a_imprimer": False,
    "kindle_joignable": False,
    "derniere_erreur": None,
    "avertissements": [],
    "livres": {},                     # nom -> sha256
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read() -> dict:
    with _LOCK:
        if _PATH.exists():
            try:
                data = json.loads(_PATH.read_text(encoding="utf-8"))
                return {**DEFAULT, **data}
            except json.JSONDecodeError:
                pass
        return dict(DEFAULT)


def update(**changes) -> dict:
    with _LOCK:
        data = dict(DEFAULT)
        if _PATH.exists():
            try:
                data.update(json.loads(_PATH.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
        data.update(changes)
        data["a_jour"] = bool(data["version_nas"]) and data["version_nas"] == data["version_kindle"]
        data["papier_a_imprimer"] = bool(data["version_papier"]) and (
            data["version_papier"] != data["version_papier_imprimee"]
        )
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(_PATH) + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_PATH)
        return data
