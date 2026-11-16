"""Réglages d'usage du kit, sauvegarde chez l'Anneau et restauration (2.5.0, contrat de sauvegarde 1).

Le kit n'avait aucun réglage d'usage dans la stack : ses réglages vivent déjà dans `/data/config/config.yaml`,
changés par l'écran Réglages (`ecrits.enregistrer_reglages`). Ce stockage reste ; ce module les présente à plat
pour la sauvegarde (`GET /externe/sauvegarde`, lue chaque nuit par l'Anneau avec le jeton commun) et pour
« Restaurer » (relire une sauvegarde chez l'Anneau, montrer les différences, les appliquer).

Ne sortent jamais du kit : rien qui touche aux papiers (ni leur mot de passe, ni les papiers conseillés écartés),
à la clé SSH ou à la connexion SSH (utilisateur de la liseuse), aux mots de passe, ni au fichier des contacts.
"""
from __future__ import annotations

import re

from .config import Config

APPLI = "kit-urgence"
JOUR = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Réglages d'usage sauvegardés : clé à plat → (section du config.yaml ou None, clé dans cette section)
_PLACES = {
    "titre_foyer": (None, "titre_foyer"),
    "liseuse_adresse": ("liseuse", "host"),
    "liseuse_port": ("liseuse", "port"),
    "liseuse_utilisateur": ("liseuse", "user"),
    "liseuse_dossier": ("liseuse", "dossier"),
    "scrutation_secondes": (None, "scrutation_secondes"),
}

# Liste explicite des clés qui ne sortent jamais du kit, même si un jour elles entraient dans le dictionnaire
EXCLUS = (
    "liseuse_utilisateur",       # identifiant de la connexion SSH à la liseuse
    "mot_de_passe_papiers",      # mot de passe du livre des papiers (stack seulement)
    "papiers_password",
    "papiers_conseilles",        # lignes écartées de la liste des papiers conseillés
    "cle_publique",              # clé SSH du kit
    "cle_ssh",
    "contacts_vcf",              # fichier des contacts déposé par carnet
)


def actuels(cfg: Config) -> dict:
    """Réglages d'usage du kit, à plat (l'utilisateur SSH y est, il est écarté par EXCLUS à la sortie)."""
    return {
        "titre_foyer": cfg.titre_foyer,
        "liseuse_adresse": cfg.kindle.host,
        "liseuse_port": cfg.kindle.port,
        "liseuse_utilisateur": cfg.kindle.user,
        "liseuse_dossier": cfg.kindle.dossier,
        "scrutation_secondes": cfg.scrutation_secondes,
    }


def corps_ecran(plats: dict) -> dict:
    """Réglages à plat → corps attendu par `ecrits.enregistrer_reglages` (même forme que l'écran)."""
    corps: dict = {"liseuse": {}}
    for cle, valeur in plats.items():
        section, nom = _PLACES[cle]
        if section:
            corps[section][nom] = valeur
        else:
            corps[nom] = valeur
    return corps
