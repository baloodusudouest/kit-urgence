"""Mode lecture seule : le kit lit tout, fabrique ses livres chez lui,
mais n'écrit ni sur la liseuse ni dans ses sources.

2.4 : MAISON_LECTURE_SEULE=oui met toute la maison en lecture seule ; KIT_LECTURE_SEULE, si elle dit oui
(« 1 » accepté comme avant) ou non, l'emporte pour le kit seul (module commun `maison`).

Le refus se fait deux fois : à l'adresse appelée, puis dans la fonction qui écrit."""
from __future__ import annotations

from . import maison

PROPRE = "KIT_LECTURE_SEULE"


class LectureSeule(Exception):
    """Écriture refusée : le kit tourne en lecture seule."""


def lecture_seule() -> bool:
    return maison.lecture_seule(PROPRE)


def origine() -> str:
    """« maison » (toute la maison), « appli » (le kit seul) ou « » (écriture permise)."""
    return maison.origine_lecture_seule(PROPRE)


def exiger_ecriture(quoi: str = "") -> None:
    if lecture_seule():
        raise LectureSeule(f"Mode lecture seule : rien n'est écrit{' ' + quoi if quoi else ''}.")
