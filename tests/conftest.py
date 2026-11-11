"""Jeu inventé commun aux tests : dossiers temporaires, fausse liseuse, aucun vrai nom.

Les chemins du kit sont lus à l'import : l'environnement est donc posé ici, avant tout import de `app`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
BASE = Path(tempfile.mkdtemp(prefix="kit-tests-"))
MDP_PAPIERS = "papiers-essai"
JETON = "jeton-essai"
MDP = "mot-de-passe-essai"

os.environ.update({
    "KIT_DATA": str(BASE / "data"), "KIT_STATE": str(BASE / "state"), "KIT_ASSETS": str(RACINE / "assets"),
    "PAPIERS_PASSWORD": MDP_PAPIERS, "API_TOKEN": JETON, "KIT_PASSWORD": MDP,
    "KIT_SANS_SCRUTATION": "1", "KIT_SANS_ATTENTE": "1",
})

import pytest  # noqa: E402

VCF = """BEGIN:VCARD
VERSION:3.0
UID:uid-plombier
FN:Plomberie du Coteau
ORG:Plomberie du Coteau
TEL;TYPE=WORK:05 55 00 00 01
END:VCARD
BEGIN:VCARD
VERSION:3.0
UID:uid-voisine
FN:Camille Voisin
TEL;TYPE=CELL:06 00 00 00 02
END:VCARD
"""

def _png() -> bytes:
    """Un « scan » inventé : petite image grise."""
    import io

    from PIL import Image
    tampon = io.BytesIO()
    Image.new("RGB", (60, 40), (200, 200, 200)).save(tampon, "PNG")
    return tampon.getvalue()


PNG = _png()


def poser_jeu() -> None:
    """Remet les dossiers dans l'état de départ : fichiers du dépôt + contacts + un papier."""
    for d in (BASE / "data", BASE / "state"):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    shutil.copytree(RACINE / "seed", BASE / "data", dirs_exist_ok=True)
    (BASE / "data" / "config" / "contacts-urgence.vcf").write_text(VCF, encoding="utf-8")
    (BASE / "data" / "papiers").mkdir(exist_ok=True)
    (BASE / "data" / "papiers" / "01-carte.png").write_bytes(PNG)
    liseuse = BASE / "liseuse"
    shutil.rmtree(liseuse, ignore_errors=True)
    cfg = BASE / "data" / "config" / "config.yaml"
    cfg.write_text(
        'titre_foyer: "Maison des Tilleuls"\n'
        f'kindle:\n  host: "127.0.0.1"\n  port: 2222\n  user: root\n  dossier: {liseuse}\n'
        "scrutation_secondes: 60\ncontacts_vcf: contacts-urgence.vcf\n", encoding="utf-8")


class FausseLiseuse:
    """Remplace la session SSH : les commandes du kit sont jouées dans un shell local.

    Le dossier de la liseuse est un dossier temporaire ; `joignable` simule sa présence."""

    def __init__(self):
        self.joignable = True
        self.commandes: list[str] = []

    def close(self):
        pass


def brancher_liseuse(monkeypatch) -> FausseLiseuse:
    from app import sync
    fausse = FausseLiseuse()

    def _exec(client, cmd, donnees=None):
        fausse.commandes.append(cmd)
        entree = donnees.read_bytes() if donnees is not None else b""
        r = subprocess.run(["sh", "-c", cmd], input=entree, capture_output=True)
        return r.returncode, r.stdout.decode("utf-8", errors="replace")

    monkeypatch.setattr(sync, "_connexion", lambda cfg: fausse)
    monkeypatch.setattr(sync, "_exec", _exec)
    monkeypatch.setattr(sync, "port_ouvert", lambda cfg, delai=2.0: fausse.joignable)
    return fausse


@pytest.fixture()
def jeu():
    poser_jeu()
    yield BASE


@pytest.fixture()
def liseuse(jeu, monkeypatch):
    return brancher_liseuse(monkeypatch)
