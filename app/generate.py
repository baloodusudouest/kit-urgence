"""Génération du kit : EPUB 00/01/02, guides 04, PDF chiffré 05, version papier, manifest.

Chaque livre n'est reconstruit que si ses entrées ont changé (empreinte des sources),
ce qui garde sa date de génération et évite de renvoyer au Kindle ce qui n'a pas bougé.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from . import config, contacts, controle, papiers, status
from .config import ASSETS, DATA, STATE, Config

TZ = ZoneInfo("Europe/Paris")
SORTIE = DATA / "output" / "Urgence"
SORTIE_PAPIER = DATA / "output" / "papier"
REGISTRE = STATE / "livres.json"

NOM_00 = "00 - Lisez-moi d'abord.epub"
NOM_01 = "01 - Procédures maison.epub"
NOM_02 = "02 - Contacts.epub"
NOM_05 = "05 - Papiers (chiffré).pdf"
NOM_PAPIER = "kit-urgence-a-imprimer.pdf"
# 2.5.7 (audit, M43) : délais maximaux des outils, sous le verrou global du kit
DELAI_PANDOC = 300        # secondes pour fabriquer un livre


# ---------------------------------------------------------------- utilitaires

def sha_fichier(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def sha_entrees(*elements) -> str:
    """Empreinte d'un ensemble d'entrées : fichiers (contenu + nom) et chaînes."""
    h = hashlib.sha256()
    for e in elements:
        if isinstance(e, Path):
            h.update(str(e.name).encode())
            h.update(sha_fichier(e).encode() if e.exists() else b"absent")
        else:
            h.update(str(e).encode())
    return h.hexdigest()


def date_fr(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%d/%m/%Y à %Hh%M")


def page_de_garde(titre: str, dt: datetime, foyer: str) -> str:
    return (
        f"# {titre}\n\n"
        f"**Kit d'urgence — {foyer}**\n\n"
        f"Généré le **{date_fr(dt)}**.\n\n"
        "> Si cette date a plus d'un mois, méfiez-vous : "
        "certaines informations peuvent avoir changé.\n\n"
    )


def epub(markdown: str, titre: str, cible: Path, ident: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "livre.md"
        src.write_text(markdown, encoding="utf-8")
        subprocess.run(
            [
                "pandoc", str(src), "-f", "markdown", "-t", "epub3", "-o", str(cible),
                "--toc", "--toc-depth=2", "--split-level=1",
                "--css", str(ASSETS / "kindle.css"),
                "--metadata", f"title={titre}",
                "--metadata", "lang=fr-FR",
                "--metadata", f"identifier=urn:kit-urgence:{ident}",
                "--metadata", "author=Kit d'urgence",
            ],
            check=True, capture_output=True, timeout=DELAI_PANDOC,
        )


def pdf_papier(markdown: str, cible: Path) -> None:
    from weasyprint import HTML  # import tardif : lourd

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "papier.md"
        html = Path(tmp) / "papier.html"
        src.write_text(markdown, encoding="utf-8")
        subprocess.run(
            [
                "pandoc", str(src), "-f", "markdown", "-t", "html5", "-s", "-o", str(html),
                "--css", str(ASSETS / "print.css"), "--embed-resources",
                "--metadata", "title=Kit d'urgence — version papier",
                "--metadata", "lang=fr-FR",
            ],
            check=True, capture_output=True, timeout=DELAI_PANDOC,
        )
        HTML(filename=str(html)).write_pdf(str(cible))


def _raison(exc: Exception) -> str:
    """Raison d'un échec de fabrication, dite en clair."""
    if isinstance(exc, controle.Echec):
        return str(exc)
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"fabrication arrêtée : plus de {exc.timeout:.0f} s sans finir"
    return f"fabrication impossible ({exc.__class__.__name__})"


# ---------------------------------------------------------------- registre

def _registre() -> dict:
    if REGISTRE.exists():
        return json.loads(REGISTRE.read_text(encoding="utf-8"))
    return {}


def _sauver_registre(reg: dict) -> None:
    REGISTRE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRE.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- guides

def charger_guides(avert: list[str]) -> list[dict]:
    path = DATA / "config" / "guides.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    valides = []
    for i, g in enumerate(data.get("guides", []), start=1):
        nom = g.get("titre") or g.get("fichier") or f"entrée {i}"
        if not g.get("editeur") or not g.get("url"):
            avert.append(f"Guide « {nom} » refusé : éditeur ou URL officielle manquant.")
            continue
        fichier = DATA / "guides" / str(g.get("fichier", ""))
        if not g.get("fichier") or not fichier.exists():
            avert.append(f"Guide « {nom} » : fichier introuvable dans guides/.")
            continue
        valides.append({**g, "_path": fichier})
    return valides


# ---------------------------------------------------------------- génération

def generer(cfg: Config, forcer: bool = False) -> dict:
    """Construit le kit dans output/. Retourne le statut mis à jour."""
    SORTIE.mkdir(parents=True, exist_ok=True)
    SORTIE_PAPIER.mkdir(parents=True, exist_ok=True)
    reg = {} if forcer else _registre()
    maintenant = datetime.now(TZ)
    avert: list[str] = []
    attendus: dict[str, dict] = {}  # nom -> {"entree": hash, "construire": callable}

    proc_dir = DATA / "procedures"
    md_00 = sorted(proc_dir.glob("00*.md"))
    md_01 = sorted(p for p in proc_dir.glob("*.md") if not p.name.startswith("00"))
    vcf = DATA / "config" / cfg.contacts_vcf
    publics = DATA / "config" / "numeros-publics.yaml"

    def texte(fichiers: list[Path]) -> str:
        return "\n\n".join(f.read_text(encoding="utf-8") for f in fichiers)

    # 00 et 01 : Markdown
    for nom, fichiers, titre, ident in [
        (NOM_00, md_00, "00 – Lisez-moi d'abord", "00"),
        (NOM_01, md_01, "01 – Procédures maison", "01"),
    ]:
        if not fichiers:
            avert.append(f"{nom} : aucun fichier Markdown dans procedures/.")
            continue
        attendus[nom] = {
            "entree": sha_entrees(cfg.titre_foyer, *fichiers),
            "construire": lambda c, f=fichiers, t=titre, i=ident: epub(
                page_de_garde(t, maintenant, cfg.titre_foyer) + texte(f), t, c, i),
        }

    # 02 : contacts
    if not vcf.exists():
        avert.append(f"Contacts : config/{cfg.contacts_vcf} absent (export du groupe iCloud).")
    attendus[NOM_02] = {
        "entree": sha_entrees(cfg.titre_foyer, vcf, publics),
        "construire": lambda c: epub(
            page_de_garde("02 – Contacts", maintenant, cfg.titre_foyer)
            + contacts.markdown(vcf, publics), "02 – Contacts", c, "02"),
    }

    # 04 : guides officiels, copiés sans modification
    for i, g in enumerate(charger_guides(avert)):
        lettre = chr(ord("a") + i)
        ext = g["_path"].suffix.lower()
        nom = f"04{lettre} - {g.get('titre', g['_path'].stem)}{ext}".replace("/", "-")
        attendus[nom] = {
            "entree": sha_entrees(g["_path"]),
            "construire": lambda c, p=g["_path"]: shutil.copyfile(p, c),
        }

    # 05 : papiers chiffrés (le mot de passe fait partie de l'empreinte, sans être stocké)
    docs = papiers.sources(DATA / "papiers")
    if docs:
        if cfg.papiers_probleme:            # mot de passe absent : livre non fabriqué, dit en clair
            avert.append(f"05 – Papiers non généré : {cfg.papiers_probleme}.")
        else:
            if cfg.papiers_avertissement:   # 2.6.1 : court, fabriqué quand même
                avert.append(f"05 – Papiers : {cfg.papiers_avertissement}.")
            attendus[NOM_05] = {
                "entree": entree_papiers(cfg, docs),
                "construire": lambda c: papiers.construire(
                    DATA / "papiers", c, cfg.papiers_password),
            }

    # Construction des livres dont les entrées ont changé.
    # 2.0.0 : chaque livre fabriqué est rouvert avant de remplacer l'ancien ; s'il est inutilisable,
    # le dernier bon livre reste en place et l'échec est noté.
    ancien_reg = _registre()
    nouveau_reg = {}
    echecs: list[dict] = []
    for nom, info in attendus.items():
        cible = SORTIE / nom
        ancien = reg.get(nom)
        if ancien and ancien.get("entree") == info["entree"] and cible.exists():
            nouveau_reg[nom] = ancien
            continue
        tmp = SORTIE / f".{nom}.tmp"
        try:
            info["construire"](tmp)
            controle.verifier(nom, tmp, cfg.papiers_password, est_papiers=(nom == NOM_05),
                              pages=len(docs) if nom == NOM_05 else None)
        except Exception as exc:  # noqa: BLE001 — un livre raté ne doit pas arrêter les autres
            tmp.unlink(missing_ok=True)
            echecs.append({"livre": nom, "raison": _raison(exc)})
            if cible.exists() and ancien_reg.get(nom):
                # L'ancien livre reste, avec son ancienne empreinte d'entrée : il sera retenté
                nouveau_reg[nom] = ancien_reg[nom]
            continue
        tmp.replace(cible)
        nouveau_reg[nom] = {
            "entree": info["entree"], "sha": sha_fichier(cible),
            "date": maintenant.isoformat(timespec="seconds"),
        }

    # Livres qui ne sont plus attendus. 2.0.0 : le kit ne retire jamais seul un livre (il serait
    # ensuite effacé de la liseuse). Il le garde, le signale, et attend un oui donné à l'écran.
    acceptees = set(status.read().get("disparitions_acceptees") or [])
    disparitions: list[str] = []
    for p in sorted(SORTIE.iterdir()):
        if not p.is_file() or p.name in attendus or p.name == "manifest.json" or p.name.startswith("."):
            continue
        if p.name in acceptees:
            p.unlink()
            continue
        disparitions.append(p.name)
        nouveau_reg[p.name] = ancien_reg.get(p.name) or {
            "entree": "retiré", "sha": sha_fichier(p),
            "date": datetime.fromtimestamp(p.stat().st_mtime, TZ).isoformat(timespec="seconds"),
        }
    for p in SORTIE.glob(".*.tmp"):
        p.unlink(missing_ok=True)

    # Manifest : empreinte globale déterministe
    livres = {nom: nouveau_reg[nom]["sha"] for nom in sorted(nouveau_reg)}
    version = hashlib.sha256(json.dumps(livres, sort_keys=True).encode()).hexdigest()
    manifest = {"version": version, "livres": livres}
    tmp_manifest = SORTIE / ".manifest.json.tmp"
    tmp_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_manifest.replace(SORTIE / "manifest.json")

    # Version papier : 00 + 01 + 02, reconstruite seulement si ses entrées changent
    entree_papier = sha_entrees(
        *(attendus[n]["entree"] for n in (NOM_00, NOM_01, NOM_02) if n in attendus))
    cible_papier = SORTIE_PAPIER / NOM_PAPIER
    if reg.get("__papier__", {}).get("entree") != entree_papier or not cible_papier.exists():
        parties = [page_de_garde("Kit d'urgence — version papier", maintenant, cfg.titre_foyer)]
        parties.append(
            "> Le mot de passe du livre 05 – Papiers n'est pas imprimé ici : "
            "il est sur la fiche manuscrite rangée à part.\n")
        if md_00:
            parties.append(texte(md_00))
        if md_01:
            parties.append(texte(md_01))
        parties.append(contacts.markdown(vcf, publics))
        tmp_papier = SORTIE_PAPIER / f".{NOM_PAPIER}.tmp"
        try:
            pdf_papier("\n\n".join(parties), tmp_papier)
            controle.verifier(NOM_PAPIER, tmp_papier)
            tmp_papier.replace(cible_papier)
        except Exception as exc:  # noqa: BLE001
            tmp_papier.unlink(missing_ok=True)
            echecs.append({"livre": NOM_PAPIER, "raison": _raison(exc)})
            entree_papier = reg.get("__papier__", {}).get("entree") or ancien_reg.get("__papier__", {}).get("entree")
    nouveau_reg["__papier__"] = {"entree": entree_papier}
    _sauver_registre(nouveau_reg)

    return status.update(
        derniere_generation=status.now(),
        derniere_erreur=None,  # génération réussie : une ancienne erreur ne reste plus affichée dans HA
        version_nas=version,
        version_papier=entree_papier,
        livres=livres,
        avertissements=avert,
        sources=sha_sources(cfg),
        controle={"le": status.now(), "ok": not echecs, "echecs": echecs},
        disparitions=disparitions,
        disparitions_acceptees=[],
    )


def instantane_papier(cfg: Config) -> dict:
    """Empreinte de chaque source de la version papier, pour dire ce qui a changé depuis l'impression."""
    proc_dir = DATA / "procedures"
    photo = {f"Texte « {p.stem} »": sha_fichier(p) for p in sorted(proc_dir.glob("*.md"))}
    photo["Contacts"] = sha_entrees(DATA / "config" / cfg.contacts_vcf)
    photo["Numéros publics"] = sha_entrees(DATA / "config" / "numeros-publics.yaml")
    photo["Nom du foyer"] = sha_entrees(cfg.titre_foyer)
    return photo


def entree_papiers(cfg: Config, docs: list[Path], ancienne: bool = False) -> str:
    """Empreinte d'entrée du livre des papiers. 2.5.7 (M45) : le mot de passe y entre par son empreinte
    lente et salée ; `ancienne` refait le calcul d'avant (SHA-256 simple) pour reprendre l'ancien registre."""
    pw = (config.empreinte_papiers_ancienne if ancienne else config.empreinte_papiers)(cfg.papiers_password)
    return sha_entrees(pw, *docs)


def sha_sources(cfg: Config, ancienne: bool = False) -> str:
    """Empreinte de toutes les sources, pour savoir s'il faut régénérer avant une livraison.
    `ancienne` : le calcul d'avant la 2.5.7 (mot de passe en SHA-256 simple), pour la reprise."""
    fichiers = []
    for sous in ("config", "procedures", "guides", "papiers"):
        d = DATA / sous
        if d.exists():
            fichiers += sorted(p for p in d.rglob("*") if p.is_file())
    pw = (config.empreinte_papiers_ancienne(cfg.papiers_password) if ancienne
          else config.empreinte_papiers(cfg.papiers_password))
    h = hashlib.sha256(pw.encode())
    for f in fichiers:
        h.update(str(f.relative_to(DATA)).encode())
        h.update(f"{f.stat().st_size}:{f.stat().st_mtime_ns}".encode())
    return h.hexdigest()


def reprendre_empreintes_anciennes(cfg: Config) -> int:
    """2.5.7 (M45), au démarrage : les empreintes rapides d'avant (registre du livre des papiers, sources,
    essai en vrai) sont relues une fois et réécrites en empreintes lentes et salées. Sans cela, le livre
    des papiers serait refait (nouvelle date, renvoi à la liseuse) et l'essai en vrai redemandé.
    Retourne le nombre d'empreintes réécrites."""
    from .config import empreinte_essai_ancienne
    n = 0
    mdp = cfg.papiers_password
    reg = _registre()
    docs = papiers.sources(DATA / "papiers")
    if mdp and docs and NOM_05 in reg and reg[NOM_05].get("entree") == entree_papiers(cfg, docs, ancienne=True):
        reg[NOM_05] = {**reg[NOM_05], "entree": entree_papiers(cfg, docs)}
        _sauver_registre(reg)
        n += 1
    etat = status.read()
    changes = {}
    if etat.get("sources") and etat.get("sources") == sha_sources(cfg, ancienne=True):
        changes["sources"] = sha_sources(cfg)
    essai = etat.get("essai") or {}
    if mdp and essai.get("mot_de_passe") and essai.get("mot_de_passe") == empreinte_essai_ancienne(mdp):
        changes["essai"] = {**essai, "mot_de_passe": config.empreinte_papiers(mdp)}
    if changes:
        status.update(**changes)
        n += len(changes)
    return n
