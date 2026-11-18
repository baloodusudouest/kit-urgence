"""Configuration du générateur kit-urgence.

Deux sources :
- variables d'environnement (secrets et chemins, définies dans la stack / .env) ;
- /data/config/config.yaml (réglages d'usage, changés dans l'écran Réglages ; sauvegardés chez l'Anneau, 2.5).
"""
from __future__ import annotations

import hashlib
import os
import secrets
import threading
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import maison

DATA = Path(os.environ.get("KIT_DATA", "/data"))
STATE = Path(os.environ.get("KIT_STATE", "/state"))
ASSETS = Path(os.environ.get("KIT_ASSETS", "/app/assets"))
PAPIERS_MIN = 12   # 2.5.7 (audit, M45) : longueur minimale du mot de passe des papiers


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

    @property
    def papiers_probleme(self) -> str:
        """Pourquoi le livre des papiers ne peut pas être chiffré ("" : rien ne l'empêche).
        2.5.7 (M45) : un mot de passe trop court est refusé comme un mot de passe absent ;
        le reste du kit démarre et se fabrique quand même."""
        mdp = self.papiers_password
        if not mdp:
            return "le mot de passe des papiers est absent de la stack (PAPIERS_PASSWORD)"
        if len(mdp) < PAPIERS_MIN:
            return (f"le mot de passe des papiers (PAPIERS_PASSWORD) est trop court : "
                    f"{PAPIERS_MIN} caractères au moins")
        return ""


# ---------------------------------------------------------------- empreinte du mot de passe des papiers
# 2.5.7 (audit, M45) : l'empreinte du mot de passe des papiers gardée sur disque (registre des livres, état)
# est lente (PBKDF2, 200 000 tours) et salée par un sel tiré au hasard une fois, propre à cette installation
# (/state/sel-papiers). Avant : un SHA-256 simple, qu'on pouvait essayer à grande vitesse.
SEL_PAPIERS = STATE / "sel-papiers"
TOURS_PAPIERS = 200_000
_EMPREINTES: dict[tuple[str, str], str] = {}
_VERROU_SEL = threading.Lock()


def _sel_papiers() -> str:
    with _VERROU_SEL:
        try:
            sel = SEL_PAPIERS.read_text(encoding="utf-8").strip()
        except OSError:
            sel = ""
        if len(sel) < 32:
            sel = secrets.token_hex(16)
            SEL_PAPIERS.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(SEL_PAPIERS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(sel)
        return sel


def empreinte_papiers(mot_de_passe: str) -> str:
    """Empreinte lente et salée du mot de passe des papiers ("" s'il est vide). Gardée en mémoire :
    calculée une fois par démarrage."""
    if not mot_de_passe:
        return ""
    sel = _sel_papiers()
    cle = (mot_de_passe, sel)
    if cle not in _EMPREINTES:
        _EMPREINTES.clear()
        _EMPREINTES[cle] = "pbkdf2:" + hashlib.pbkdf2_hmac(
            "sha256", mot_de_passe.encode(), bytes.fromhex(sel), TOURS_PAPIERS).hex()
    return _EMPREINTES[cle]


def empreinte_papiers_ancienne(mot_de_passe: str) -> str:
    """Empreinte rapide d'avant la 2.5.7 (SHA-256 simple) : relue une fois pour reprendre l'ancien état,
    jamais réécrite."""
    return hashlib.sha256(mot_de_passe.encode()).hexdigest()


def empreinte_essai_ancienne(mot_de_passe: str) -> str:
    """Empreinte de l'essai en vrai d'avant la 2.5.7 (scrypt à sel fixe) : relue une fois, jamais réécrite."""
    return hashlib.scrypt(mot_de_passe.encode(), salt=b"kit-urgence-essai", n=2**14, r=8, p=1, dklen=16).hex()


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
