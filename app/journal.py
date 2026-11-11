"""Journal des gestes faits depuis l'écran ou par jeton. Jamais de nom de papier ni de contact."""
from __future__ import annotations

import json
import threading

from . import status
from .config import STATE

_PATH = STATE / "journal.jsonl"
_LOCK = threading.Lock()
GARDEES = 300


def noter(quoi: str, par: str = "écran") -> None:
    ligne = json.dumps({"le": status.now(), "par": par, "quoi": quoi}, ensure_ascii=False)
    with _LOCK:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        lignes = _PATH.read_text(encoding="utf-8").splitlines() if _PATH.exists() else []
        lignes = (lignes + [ligne])[-GARDEES:]
        tmp = _PATH.with_suffix(".tmp")
        tmp.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        tmp.replace(_PATH)


def lire(nombre: int = 50) -> list[dict]:
    if not _PATH.exists():
        return []
    sortie = []
    for ligne in _PATH.read_text(encoding="utf-8").splitlines()[-nombre:]:
        try:
            sortie.append(json.loads(ligne))
        except json.JSONDecodeError:
            continue
    return sortie[::-1]
