"""Mode lecture seule (KIT_LECTURE_SEULE) : le kit lit tout, fabrique ses livres chez lui,
mais n'écrit ni sur la liseuse ni dans ses sources.

Le refus se fait deux fois : à l'adresse appelée, puis dans la fonction qui écrit."""
from __future__ import annotations

import os

VRAI = ("oui", "1", "true", "yes")


class LectureSeule(Exception):
    """Écriture refusée : le kit tourne en lecture seule."""


def lecture_seule() -> bool:
    return os.environ.get("KIT_LECTURE_SEULE", "").strip().lower() in VRAI


def exiger_ecriture(quoi: str = "") -> None:
    if lecture_seule():
        raise LectureSeule(f"Mode lecture seule : rien n'est écrit{' ' + quoi if quoi else ''}.")
