"""Configuration du générateur kit-urgence.

Deux sources :
- variables d'environnement (secrets et chemins, définies dans la stack / .env) ;
- /data/config/config.yaml (réglages d'usage, changés dans l'écran Réglages ; sauvegardés chez l'Anneau, 2.5).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import maison

DATA = Path(os.environ.get("KIT_DATA", "/data"))
STATE = Path(os.environ.get("KIT_STATE", "/state"))
ASSETS = Path(os.environ.get("KIT_ASSETS", "/app/assets"))


@dataclass
class KindleCfg:
    host: str = ""
    port: int = 2222
    user: str = "root"
    dossier: str = "/mnt/us/documents/Urgence"


@dataclass
class Config:
    kindle: KindleCfg = field(default_factory=KindleCfg)
    # Intervalle de scrutation du port SSH du Kindle (secondes)
    scrutation_secondes: int = 60
    # Fichier .vcf exporté depuis iCloud (groupe « Urgence »), relatif à config/
    contacts_vcf: str = "contacts-urgence.vcf"
    titre_foyer: str = "Maison"

    @property
    def papiers_password(self) -> str:
        # Jamais dans les fichiers : uniquement en variable d'environnement
        return os.environ.get("PAPIERS_PASSWORD", "")


def mot_de_passe() -> str:
    """Mot de passe commun de l'interface. Sans lui (ou trop court), le kit refuse de démarrer.
    2.5 : MAISON_PASSWORD seul (l'ancien KIT_PASSWORD n'est plus lu)."""
    return maison.mot_de_passe()


# 2.4 : adresses des autres applis, lues dans l'Anneau (un seul annuaire pour tout le kit)
ANNUAIRE = maison.Annuaire()


def carnet_url(prive: bool = False) -> str:
    """Adresse de carnet dans le navigateur, pour le lien « Ouvrir dans carnet » (facultative).
    Lue dans l'Anneau seulement (tuile « carnet » ; adresse privée quand la page vient de Tailscale).
    2.5 : plus de repli KIT_CARNET_URL ; Anneau muet et rien de connu = pas de lien."""
    return ANNUAIRE.adresse("carnet", prive=prive, repli="").strip().rstrip("/")


def load() -> Config:
    path = DATA / "config" / "config.yaml"
    raw = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = Config()
    k = raw.get("kindle", {}) or {}
    cfg.kindle = KindleCfg(
        host=str(k.get("host", cfg.kindle.host)),
        port=int(k.get("port", cfg.kindle.port)),
        user=str(k.get("user", cfg.kindle.user)),
        dossier=str(k.get("dossier", cfg.kindle.dossier)),
    )
    cfg.scrutation_secondes = int(raw.get("scrutation_secondes", cfg.scrutation_secondes))
    cfg.contacts_vcf = str(raw.get("contacts_vcf", cfg.contacts_vcf))
    cfg.titre_foyer = str(raw.get("titre_foyer", cfg.titre_foyer))
    return cfg
