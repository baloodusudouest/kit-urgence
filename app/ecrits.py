"""Tout ce que l'écran écrit dans les sources du kit (2.1.0).

Règles communes :
- lecture seule refusée ici aussi (`exiger_ecriture`), au plus près du fichier ;
- écriture atomique (fichier à côté, puis bascule) ;
- avant de réécrire un texte ou un réglage, l'ancien est gardé dans `/data/versions/` (dix dernières) ;
- on n'écrase jamais un fichier déposé ; un papier ou un guide retiré est mis de côté dans
  `/data/retires/`, hors des dossiers que le générateur parcourt ;
- un nom donné par l'écran ne sert jamais de chemin : il est nettoyé, puis cherché dans le dossier prévu.
Enregistrer ne fabrique rien : le kit devient « à refabriquer »."""
from __future__ import annotations

import re
import shutil
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from . import papiers as livre_papiers
from .config import DATA
from .garde import exiger_ecriture

VERSIONS = DATA / "versions"
RETIRES = DATA / "retires"
GARDEES = 10
Mo = 1024 * 1024
MAX_PAPIER = 50 * Mo
MAX_GUIDE = 150 * Mo
MAX_TEXTE = 400_000

EXT_PAPIERS = {".pdf", ".jpg", ".jpeg", ".png"}
EXT_GUIDES = {".pdf", ".epub"}
NOM_TEXTE = re.compile(r"^[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
ENTETES = {
    "numeros-publics.yaml": "# Numéros publics du livre des contacts. Écrit par l'écran du kit (Kit › Contacts).\n",
    "guides.yaml": "# Guides officiels, copiés sans modification. Écrit par l'écran du kit (Kit › Guides).\n"
                   "# Chaque guide doit avoir un éditeur ET une adresse officielle, sinon il ne part pas dans le kit.\n",
    "config.yaml": "# Réglages du kit d'urgence. Écrit par l'écran du kit (Réglages).\n",
}


class Refus(Exception):
    """Demande refusée : le message est montré tel quel à l'écran."""

    def __init__(self, message: str, code: int = 422):
        super().__init__(message)
        self.code = code


# ------------------------------------------------------------------ outils

def _horodatage() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _ecrire(chemin: Path, contenu: bytes | str) -> None:
    exiger_ecriture("dans les sources du kit")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.parent / f".{chemin.name}.ecriture"
    if isinstance(contenu, str):
        tmp.write_text(contenu, encoding="utf-8")
    else:
        tmp.write_bytes(contenu)
    tmp.replace(chemin)


def nettoyer_nom(nom: str, extensions: set[str]) -> str:
    """Nom de fichier sûr : lettres, chiffres, tirets, points ; extension parmi celles admises."""
    base = Path(str(nom).replace("\\", "/")).name
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    tige, ext = Path(base).stem, Path(base).suffix.lower()
    tige = re.sub(r"[^A-Za-z0-9._-]+", "-", tige).strip("-._")[:80]
    if not tige:
        raise Refus("Ce nom de fichier ne contient rien d'utilisable.")
    if ext not in extensions:
        raise Refus("Type de fichier refusé : " + ", ".join(sorted(e[1:].upper() for e in extensions)) + " seulement.")
    return tige + ext


def _est_du_type(contenu: bytes, ext: str) -> bool:
    if ext == ".pdf":
        return contenu[:5] == b"%PDF-"
    if ext in (".jpg", ".jpeg"):
        return contenu[:3] == b"\xff\xd8\xff"
    if ext == ".png":
        return contenu[:8] == b"\x89PNG\r\n\x1a\n"
    if ext == ".epub":
        return contenu[:2] == b"PK"
    return False


# ------------------------------------------------------------------ versions

def _dossier_versions(chemin: Path) -> Path:
    return VERSIONS / chemin.parent.name / chemin.name


def garder_version(chemin: Path) -> None:
    """Copie le fichier tel qu'il est avant qu'on le réécrive. Ne garde que les dix dernières."""
    if not chemin.is_file():
        return
    exiger_ecriture("dans les sources du kit")
    dossier = _dossier_versions(chemin)
    dossier.mkdir(parents=True, exist_ok=True)
    existantes = sorted(dossier.iterdir())
    if existantes and existantes[-1].read_bytes() == chemin.read_bytes():
        return
    shutil.copyfile(chemin, dossier / f"{_horodatage()}{chemin.suffix}")
    for vieille in sorted(dossier.iterdir())[:-GARDEES]:
        vieille.unlink()


def versions(chemin: Path) -> list[dict]:
    dossier = _dossier_versions(chemin)
    if not dossier.is_dir():
        return []
    sortie = []
    for p in sorted(dossier.iterdir(), reverse=True):
        le = datetime.strptime(p.stem, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        sortie.append({"id": p.stem, "le": le.isoformat(timespec="seconds"),
                       "mots": len(p.read_text(encoding="utf-8", errors="replace").split())})
    return sortie


def lire_version(chemin: Path, ident: str) -> str:
    for p in _dossier_versions(chemin).iterdir() if _dossier_versions(chemin).is_dir() else []:
        if p.stem == ident:
            return p.read_text(encoding="utf-8")
    raise Refus("Version introuvable.", 404)


# ------------------------------------------------------------------ textes (livres 00 et 01)

PROCEDURES = DATA / "procedures"


def _texte(nom: str) -> Path:
    for p in PROCEDURES.glob("*.md"):
        if p.name == nom:
            return p
    raise Refus("Texte introuvable.", 404)


def enregistrer_texte(nom: str, contenu: str) -> None:
    chemin = _texte(nom)
    if not isinstance(contenu, str) or not contenu.strip():
        raise Refus("Un texte vide n'est pas enregistré. Pour l'enlever du livre, supprime-le.")
    if len(contenu.encode("utf-8")) > MAX_TEXTE:
        raise Refus("Texte trop long.")
    contenu = contenu.replace("\r\n", "\n").rstrip() + "\n"
    if chemin.read_text(encoding="utf-8") == contenu:
        return
    garder_version(chemin)
    _ecrire(chemin, contenu)


def revenir_texte(nom: str, ident: str) -> None:
    chemin = _texte(nom)
    ancien = lire_version(chemin, ident)
    garder_version(chemin)                       # la version qu'on quitte reste dans la liste
    _ecrire(chemin, ancien)


def creer_texte(titre: str, numero: int) -> str:
    titre = " ".join(str(titre).split())
    if not titre:
        raise Refus("Il faut un titre.")
    if not isinstance(numero, int) or not 1 <= numero <= 99:
        raise Refus("La place dans le livre est un nombre de 1 à 99 (00 est le « Lisez-moi »).")
    tige = unicodedata.normalize("NFKD", titre).encode("ascii", "ignore").decode().lower()
    tige = re.sub(r"[^a-z0-9]+", "-", tige).strip("-")[:50]
    nom = f"{numero:02d}-{tige}.md"
    if not NOM_TEXTE.match(nom):
        raise Refus("Ce titre ne donne pas un nom de fichier utilisable.")
    if (PROCEDURES / nom).exists():
        raise Refus("Un texte porte déjà ce nom.", 409)
    _ecrire(PROCEDURES / nom, f"# {titre}\n\nÀ COMPLÉTER\n")
    return nom


def supprimer_texte(nom: str) -> None:
    chemin = _texte(nom)
    if nom.startswith("00"):
        raise Refus("Le « Lisez-moi » ne se supprime pas : c'est la première page du kit.")
    garder_version(chemin)                       # il reste dans les versions
    exiger_ecriture("dans les sources du kit")
    chemin.unlink()


# ------------------------------------------------------------------ YAML réécrits

def _ecrire_yaml(chemin: Path, donnees: dict) -> None:
    garder_version(chemin)
    corps = yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False, width=120)
    _ecrire(chemin, ENTETES.get(chemin.name, "") + corps)


def _lire_yaml(chemin: Path) -> dict:
    if not chemin.exists():
        return {}
    return yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}


# ------------------------------------------------------------------ numéros publics

NUMEROS = DATA / "config" / "numeros-publics.yaml"
_A_VERIFIER = re.compile(r"\s*[,;—-]?\s*à vérifier[^,;]*", re.IGNORECASE)


def _champ(valeur, quoi: str, maxi: int = 200, vide_admis: bool = False) -> str:
    texte = " ".join(str(valeur or "").split())
    if not texte and not vide_admis:
        raise Refus(f"Il manque : {quoi}.")
    if len(texte) > maxi:
        raise Refus(f"Trop long : {quoi}.")
    return texte


def _numero(donnees: dict, cat: int, indice: int | None = None) -> tuple[dict, list, dict | None]:
    cats = donnees.setdefault("categories", [])
    if not 0 <= cat < len(cats):
        raise Refus("Catégorie introuvable.", 404)
    liste = cats[cat].setdefault("numeros", [])
    if indice is None:
        return cats[cat], liste, None
    if not 0 <= indice < len(liste):
        raise Refus("Numéro introuvable.", 404)
    return cats[cat], liste, liste[indice]


def enregistrer_numero(cat: int, indice: int | None, corps: dict) -> None:
    donnees = _lire_yaml(NUMEROS)
    _, liste, ligne = _numero(donnees, cat, indice)
    nouveau = {"nom": _champ(corps.get("nom"), "le nom"), "numero": _champ(corps.get("numero"), "le numéro", 60)}
    note = _champ(corps.get("note"), "la note", 300, vide_admis=True)
    if note:
        nouveau["note"] = note
    if ligne is None:
        liste.append(nouveau)
    else:
        # Un numéro qui change n'est plus « vérifié »
        if ligne.get("verifie_le") and str(ligne.get("numero")) == nouveau["numero"]:
            nouveau["verifie_le"] = ligne["verifie_le"]
        liste[indice] = nouveau
    _ecrire_yaml(NUMEROS, donnees)


def numero_verifie(cat: int, indice: int) -> None:
    donnees = _lire_yaml(NUMEROS)
    _, _, ligne = _numero(donnees, cat, indice)
    if "À COMPLÉTER" in str(ligne.get("numero", "")):
        raise Refus("Ce numéro est encore à compléter.")
    ligne["verifie_le"] = date.today().isoformat()
    note = _A_VERIFIER.sub("", str(ligne.get("note", "") or "")).strip(" ,;—-")
    if note:
        ligne["note"] = note
    else:
        ligne.pop("note", None)
    _ecrire_yaml(NUMEROS, donnees)


def supprimer_numero(cat: int, indice: int) -> None:
    donnees = _lire_yaml(NUMEROS)
    _, liste, _ = _numero(donnees, cat, indice)
    del liste[indice]
    _ecrire_yaml(NUMEROS, donnees)


# ------------------------------------------------------------------ guides (livre 04)

GUIDES = DATA / "guides"
GUIDES_YAML = DATA / "config" / "guides.yaml"


def _fiche_guide(corps: dict) -> dict:
    url = _champ(corps.get("url"), "l'adresse officielle", 500)
    if not re.match(r"^https?://[^\s/]+\.[^\s/]+", url):
        raise Refus("L'adresse officielle doit commencer par http:// ou https://.")
    fiche = {"titre": _champ(corps.get("titre"), "le titre"), "editeur": _champ(corps.get("editeur"), "l'éditeur"),
             "url": url}
    for cle, maxi in (("date", 20), ("langue", 10)):
        valeur = _champ(corps.get(cle), cle, maxi, vide_admis=True)
        if valeur:
            fiche[cle] = valeur
    return fiche


def deposer_guide(nom: str, contenu: bytes, corps: dict) -> None:
    """Un guide n'entre qu'avec son titre, son éditeur et son adresse officielle."""
    fiche = _fiche_guide(corps)
    nom = nettoyer_nom(nom, EXT_GUIDES)
    if len(contenu) > MAX_GUIDE:
        raise Refus("Fichier trop lourd (150 Mo au plus).", 413)
    if not _est_du_type(contenu, Path(nom).suffix):
        raise Refus("Le contenu du fichier ne correspond pas à son extension.")
    donnees = _lire_yaml(GUIDES_YAML)
    liste = donnees.setdefault("guides", []) or []
    donnees["guides"] = liste
    deja = next((g for g in liste if g.get("fichier") == nom), None)
    if (GUIDES / nom).exists():
        raise Refus("Un guide porte déjà ce nom de fichier : retire-le d'abord, ou renomme le fichier.", 409)
    _ecrire(GUIDES / nom, contenu)
    if deja is not None:                          # fiche déclarée dont le fichier manquait
        deja.update(fiche)
    else:
        liste.append({**fiche, "fichier": nom})
    _ecrire_yaml(GUIDES_YAML, donnees)


def _guide(donnees: dict, indice: int) -> dict:
    liste = donnees.get("guides") or []
    if not 0 <= indice < len(liste):
        raise Refus("Guide introuvable.", 404)
    return liste[indice]


def enregistrer_guide(indice: int, corps: dict) -> None:
    donnees = _lire_yaml(GUIDES_YAML)
    guide = _guide(donnees, indice)
    fichier = guide.get("fichier")
    guide.clear()
    guide.update({**_fiche_guide(corps), **({"fichier": fichier} if fichier else {})})
    _ecrire_yaml(GUIDES_YAML, donnees)


def joindre_guide(indice: int, nom: str, contenu: bytes) -> None:
    """Dépose le fichier d'un guide déjà déclaré (celui qui « manque »)."""
    donnees = _lire_yaml(GUIDES_YAML)
    guide = _guide(donnees, indice)
    attendu = str(guide.get("fichier") or "")
    nom = nettoyer_nom(attendu or nom, EXT_GUIDES)
    if (GUIDES / nom).exists():
        raise Refus("Ce guide a déjà son fichier.", 409)
    if len(contenu) > MAX_GUIDE:
        raise Refus("Fichier trop lourd (150 Mo au plus).", 413)
    if not _est_du_type(contenu, Path(nom).suffix):
        raise Refus(f"Le fichier attendu est un {Path(nom).suffix[1:].upper()}.")
    _ecrire(GUIDES / nom, contenu)
    if not attendu:
        guide["fichier"] = nom
        _ecrire_yaml(GUIDES_YAML, donnees)


def retirer_guide(indice: int) -> None:
    donnees = _lire_yaml(GUIDES_YAML)
    guide = _guide(donnees, indice)
    fichier = GUIDES / str(guide.get("fichier") or "")
    exiger_ecriture("dans les sources du kit")
    if guide.get("fichier") and fichier.is_file() and fichier.parent == GUIDES:
        cote = RETIRES / "guides"
        cote.mkdir(parents=True, exist_ok=True)
        fichier.replace(cote / f"{_horodatage()}--{fichier.name}")
    donnees["guides"].remove(guide)
    _ecrire_yaml(GUIDES_YAML, donnees)


# ------------------------------------------------------------------ papiers (livre 05)

PAPIERS = DATA / "papiers"
_PREFIXE = re.compile(r"^\d+-")


def _papier(nom: str) -> Path:
    """Un papier du premier niveau du dossier, désigné par son seul nom."""
    for p in livre_papiers.sources(PAPIERS):
        if p.parent == PAPIERS and p.name == nom:
            return p
    raise Refus("Papier introuvable.", 404)


def _plats() -> list[Path]:
    """Les papiers dans l'ordre du livre. Refuse de réordonner s'il y a des sous-dossiers."""
    docs = livre_papiers.sources(PAPIERS)
    if any(p.parent != PAPIERS for p in docs):
        raise Refus("Des papiers sont rangés dans des sous-dossiers : l'ordre ne se change pas depuis l'écran.", 409)
    return docs


def deposer_papier(nom: str, contenu: bytes) -> str:
    nom = nettoyer_nom(nom, EXT_PAPIERS)
    if not contenu:
        raise Refus("Fichier vide.")
    if len(contenu) > MAX_PAPIER:
        raise Refus("Fichier trop lourd (50 Mo au plus).", 413)
    if not _est_du_type(contenu, Path(nom).suffix):
        raise Refus("Le contenu du fichier ne correspond pas à son extension.")
    # Rangé à la fin du livre : numéro suivant en tête du nom
    existants = livre_papiers.sources(PAPIERS)
    numeros = [int(m.group(0)[:-1]) for p in existants if p.parent == PAPIERS and (m := _PREFIXE.match(p.name))]
    nom = f"{(max(numeros) + 1 if numeros else len(existants) + 1):02d}-{_PREFIXE.sub('', nom)}"
    if (PAPIERS / nom).exists():
        raise Refus("Un papier porte déjà ce nom.", 409)
    _ecrire(PAPIERS / nom, contenu)
    return nom


def ordonner_papiers(noms: list[str]) -> None:
    """Réécrit les numéros en tête des noms pour que l'ordre du livre soit celui demandé."""
    docs = _plats()
    if sorted(noms) != sorted(p.name for p in docs):
        raise Refus("La liste a changé entre-temps : recharge l'écran.", 409)
    exiger_ecriture("dans les sources du kit")
    par_nom = {p.name: p for p in docs}
    provisoires = []
    for i, nom in enumerate(noms, start=1):          # deux temps : aucun nom ne peut en écraser un autre
        tmp = PAPIERS / f".ordre-{i:03d}{par_nom[nom].suffix}"
        par_nom[nom].replace(tmp)
        provisoires.append((tmp, f"{i:02d}-{_PREFIXE.sub('', nom)}"))
    for tmp, final in provisoires:
        tmp.replace(PAPIERS / final)


def renommer_papier(nom: str, nouveau: str) -> str:
    chemin = _papier(nom)
    prefixe = (_PREFIXE.match(nom) or [""])[0]
    final = prefixe + _PREFIXE.sub("", nettoyer_nom(Path(nouveau).stem + chemin.suffix, EXT_PAPIERS))
    if final == nom:
        return nom
    if (PAPIERS / final).exists():
        raise Refus("Un papier porte déjà ce nom.", 409)
    exiger_ecriture("dans les sources du kit")
    chemin.replace(PAPIERS / final)
    return final


def retirer_papier(nom: str) -> None:
    """Mis de côté, hors du dossier des papiers : il ne repart pas dans le livre, et peut être remis."""
    chemin = _papier(nom)
    exiger_ecriture("dans les sources du kit")
    cote = RETIRES / "papiers"
    cote.mkdir(parents=True, exist_ok=True)
    chemin.replace(cote / f"{_horodatage()}--{chemin.name}")


def papiers_retires() -> list[dict]:
    cote = RETIRES / "papiers"
    if not cote.is_dir():
        return []
    sortie = []
    for p in sorted(cote.iterdir(), reverse=True):
        ident, _, nom = p.name.partition("--")
        if not nom or not p.is_file():
            continue
        le = datetime.strptime(ident, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        sortie.append({"id": ident, "nom": nom, "retire_le": le.isoformat(timespec="seconds"),
                       "poids": p.stat().st_size})
    return sortie


def _retire(ident: str) -> Path:
    cote = RETIRES / "papiers"
    for p in cote.iterdir() if cote.is_dir() else []:
        if p.is_file() and p.name.partition("--")[0] == ident:
            return p
    raise Refus("Papier mis de côté introuvable.", 404)


def remettre_papier(ident: str) -> str:
    chemin = _retire(ident)
    nom = chemin.name.partition("--")[2]
    if (PAPIERS / nom).exists():
        raise Refus("Un papier porte déjà ce nom dans le livre.", 409)
    exiger_ecriture("dans les sources du kit")
    PAPIERS.mkdir(parents=True, exist_ok=True)
    chemin.replace(PAPIERS / nom)
    return nom


def effacer_papier(ident: str) -> None:
    """Effacement réel du fichier mis de côté. La corbeille du NAS et les sauvegardes peuvent en garder une copie."""
    chemin = _retire(ident)
    exiger_ecriture("dans les sources du kit")
    chemin.unlink()


# ------------------------------------------------------------------ réglages

CONFIG = DATA / "config" / "config.yaml"


def enregistrer_reglages(corps: dict) -> None:
    donnees = _lire_yaml(CONFIG)
    liseuse = corps.get("liseuse") or {}
    hote = _champ(liseuse.get("host"), "l'adresse de la liseuse", 100, vide_admis=True)
    if hote and not re.match(r"^[A-Za-z0-9][A-Za-z0-9.-]*$", hote):
        raise Refus("L'adresse de la liseuse est une adresse IP ou un nom, sans espace ni « / ».")
    try:
        port = int(liseuse.get("port", 2222))
        scrutation = int(corps.get("scrutation_secondes", 60))
    except (TypeError, ValueError):
        raise Refus("Le port et l'intervalle sont des nombres.")
    if not 1 <= port <= 65535:
        raise Refus("Port invalide.")
    if not 15 <= scrutation <= 3600:
        raise Refus("L'intervalle de recherche va de 15 à 3600 secondes.")
    dossier = _champ(liseuse.get("dossier"), "le dossier sur la liseuse", 200)
    if not re.match(r"^/[A-Za-z0-9._/ -]+$", dossier) or ".." in dossier or dossier.rstrip("/").count("/") < 2:
        raise Refus("Le dossier sur la liseuse est un chemin complet d'au moins deux niveaux, par exemple "
                    "/mnt/us/documents/Urgence : la livraison y efface les livres qui ne sont plus dans le kit.")
    utilisateur = _champ(liseuse.get("user") or "root", "l'utilisateur", 40)
    if not re.match(r"^[a-z_][a-z0-9_-]*$", utilisateur):
        raise Refus("Utilisateur invalide.")
    donnees["titre_foyer"] = _champ(corps.get("titre_foyer"), "le nom du foyer", 80)
    donnees["kindle"] = {"host": hote, "port": port, "user": utilisateur, "dossier": dossier.rstrip("/")}
    donnees["scrutation_secondes"] = scrutation
    donnees.setdefault("contacts_vcf", "contacts-urgence.vcf")
    _ecrire_yaml(CONFIG, donnees)
