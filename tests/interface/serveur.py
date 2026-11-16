"""Kit de démonstration pour les tests d'écran : jeu inventé, fausse liseuse (un dossier local).

    python -m tests.interface.serveur <port>

Mot de passe : celui de tests/conftest.py. Rien ne sort de la machine."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from tests import conftest


def main() -> None:
    port = int(sys.argv[1])
    conftest.poser_jeu()
    patch = pytest.MonkeyPatch()
    conftest.brancher_liseuse(patch)
    import os
    os.environ["MAISON_JETON"] = "jeton-commun-essai"
    from app import config, main as appli

    def faux_anneau(adresse: str, jeton: str) -> dict:
        """Deux sauvegardes inventées ; celle du 15 propose toujours un autre intervalle que l'actuel."""
        if "?le=" not in adresse:
            return {"dates": ["2026-11-15", "2026-11-14"]}
        actuel = config.load().scrutation_secondes
        return {"le": adresse.split("?le=")[1], "version": "2.5.0",
                "reglages": {"titre_foyer": config.load().titre_foyer,
                             "scrutation_secondes": 120 if actuel != 120 else 60}}
    appli.LIRE_ANNEAU = faux_anneau
    serveur = uvicorn.Server(uvicorn.Config(appli.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=serveur.run, daemon=True).start()
    Path(conftest.BASE / "pret").write_text(str(conftest.BASE))
    print(conftest.BASE, flush=True)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
