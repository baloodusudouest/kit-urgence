"""Mode lecture seule : le kit lit tout, fabrique ses livres chez lui,
mais n'écrit ni sur la liseuse ni dans ses sources.

2.4 : MAISON_LECTURE_SEULE=oui met toute la maison en lecture seule ; KIT_LECTURE_SEULE, si elle dit oui
(« 1 » accepté comme avant) ou non, l'emporte pour le kit seul (module commun `maison`).

Le refus se fait deux fois : à l'adresse appelée, puis dans la fonction qui écrit.

2.5 : une exception, les réglages internes du kit (`config.yaml` : nom du foyer, liseuse, intervalle) se changent
et se restaurent même en lecture seule (la lecture seule protège la liseuse et les sources des livres) ;
`ecrits.enregistrer_reglages` s'enveloppe dans `reglages_internes()`."""
from __future__ import annotations

import contextlib
import contextvars

from . import maison

PROPRE = "KIT_LECTURE_SEULE"
_INTERNE: contextvars.ContextVar[bool] = contextvars.ContextVar("reglages_internes", default=False)


class LectureSeule(Exception):
    """Écriture refusée : le kit tourne en lecture seule."""


def lecture_seule() -> bool:
    return maison.lecture_seule(PROPRE)


def origine() -> str:
    """« maison » (toute la maison), « appli » (le kit seul) ou « » (écriture permise)."""
    return maison.origine_lecture_seule(PROPRE)


@contextlib.contextmanager
def reglages_internes():
    """Pendant ce bloc, l'écriture des réglages internes du kit est permise même en lecture seule."""
    jeton = _INTERNE.set(True)
    try:
        yield
    finally:
        _INTERNE.reset(jeton)


def exiger_ecriture(quoi: str = "") -> None:
    if lecture_seule() and not _INTERNE.get():
        raise LectureSeule(f"Mode lecture seule : rien n'est écrit{' ' + quoi if quoi else ''}.")
