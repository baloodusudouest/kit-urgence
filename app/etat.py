"""Ce que l'écran montre : la phrase d'état, les tuiles « À traiter », les livres, les services.

Tout ici ne fait que lire. Aucun nom de papier ne sort d'ici vers `/status` ni vers le journal :
la liste des papiers n'est donnée qu'à l'écran, derrière le mot de passe."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import config, contacts, generate, papiers, status
from .config import DATA, Config

MARQUE = "À COMPLÉTER"
ESSAI_JOURS = 182            # un essai tous les six mois
LISEUSE_JOURS = 60           # liseuse pas vue depuis deux mois : elle est peut-être à plat
CONTACTS_JOURS = 182         # contacts pas reçus depuis six mois

POINTS_ESSAI = [
    {"cle": "livre", "texte": "J'ai ouvert un livre du kit sur la liseuse, et il se lit."},
    {"cle": "mot_de_passe", "texte": "J'ai ouvert le livre des papiers en tapant le mot de passe à la main."},
    {"cle": "papier", "texte": "J'ai retrouvé la version papier, et la fiche du mot de passe rangée à part."},
    {"cle": "batterie", "texte": "La liseuse est chargée, et son chargeur est rangé avec elle."},
]

TITRES = {
    generate.NOM_00: ("00", "Lisez-moi d'abord", "Par où commencer le jour où ça ne marche plus."),
    generate.NOM_01: ("01", "Procédures de la maison", "Électricité, eau, chauffage, congélateur, réseau."),
    generate.NOM_02: ("02", "Contacts", "Numéros d'urgence, services, proches et artisans."),
    generate.NOM_05: ("05", "Papiers", "Les scans des papiers, chiffrés par mot de passe."),
}


def _jours_depuis(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        quand = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if quand.tzinfo is None:
        quand = quand.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - quand).days


def _iso_fichier(p: Path) -> str | None:
    if not p.exists():
        return None
    return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")


def empreinte_mot_de_passe(mot_de_passe: str) -> str:
    """Trace courte et lente à retrouver, pour dire « le mot de passe a changé depuis l'essai »."""
    if not mot_de_passe:
        return ""
    return hashlib.scrypt(mot_de_passe.encode(), salt=b"kit-urgence-essai", n=2**14, r=8, p=1, dklen=16).hex()


# ------------------------------------------------------------------ sources

def textes() -> list[dict]:
    """Les textes des livres 00 et 01, dans l'ordre du livre."""
    sortie = []
    for p in sorted((DATA / "procedures").glob("*.md")):
        contenu = p.read_text(encoding="utf-8")
        titre = next((l.lstrip("# ").strip() for l in contenu.splitlines() if l.startswith("#")), p.stem)
        sortie.append({"nom": p.name, "titre": titre, "livre": "00" if p.name.startswith("00") else "01",
                       "modifie_le": _iso_fichier(p), "a_completer": contenu.count(MARQUE),
                       "mots": len(contenu.split())})
    return sortie


def numeros() -> list[dict]:
    """Numéros publics, avec ce qui reste à faire sur chacun."""
    chemin = DATA / "config" / "numeros-publics.yaml"
    sortie = []
    for i, cat in enumerate(contacts.lire_publics(chemin)):
        lignes = []
        for j, n in enumerate(cat.get("numeros", []) or []):
            numero, note = str(n.get("numero", "")), str(n.get("note", "") or "")
            lignes.append({
                "indice": j, "nom": n.get("nom", ""), "numero": numero, "note": note,
                "verifie_le": n.get("verifie_le"),
                "a_completer": MARQUE in numero,
                "a_verifier": "à vérifier" in note.lower() and not n.get("verifie_le") and MARQUE not in numero,
            })
        sortie.append({"indice": i, "nom": cat.get("nom", ""), "numeros": lignes})
    return sortie


def guides() -> list[dict]:
    """Les guides déclarés, avec ce qui manque à chacun (fichier, éditeur, adresse officielle)."""
    chemin = DATA / "config" / "guides.yaml"
    if not chemin.exists():
        return []
    data = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    sortie = []
    for i, g in enumerate(data.get("guides", []) or []):
        fichier = str(g.get("fichier", "") or "")
        present = bool(fichier) and (DATA / "guides" / fichier).is_file()
        manques = []
        if not g.get("editeur"):
            manques.append("éditeur")
        if not g.get("url"):
            manques.append("adresse officielle")
        if not present:
            manques.append("fichier")
        sortie.append({"indice": i, "titre": g.get("titre") or fichier or f"guide {i + 1}", "fichier": fichier,
                       "editeur": g.get("editeur", ""), "url": g.get("url", ""), "date": str(g.get("date", "") or ""),
                       "langue": g.get("langue", ""), "present": present, "manques": manques})
    return sortie


def liste_contacts(cfg: Config) -> dict:
    chemin = DATA / "config" / cfg.contacts_vcf
    base = config.carnet_url()
    lignes = [{"nom": c["nom"], "organisation": c["organisation"], "tels": c["tels"],
               "carnet": f"{base}/#/contacts/{c['uid']}" if base and c.get("uid") else None}
              for c in contacts.lire_vcf(chemin)]
    return {"contacts": lignes, "recus_le": _iso_fichier(chemin), "carnet": base or None}


def liste_papiers() -> list[dict]:
    """Noms seulement, dans l'ordre du livre. Ni aperçu, ni téléchargement."""
    dossier = DATA / "papiers"
    return [{"nom": str(p.relative_to(dossier)), "poids": p.stat().st_size} for p in papiers.sources(dossier)]


# ------------------------------------------------------------------ livres

def livres(cfg: Config) -> list[dict]:
    etat = status.read()
    registre = generate._registre()
    echecs = {e["livre"]: e["raison"] for e in (etat.get("controle") or {}).get("echecs", [])}
    disparitions = set(etat.get("disparitions") or [])
    sortie = []
    # 2.1.3 : les livres de base sont toujours montrés, même pas encore fabriqués — c'est dans le livre
    # des papiers que l'on dépose les papiers : il doit être là avant le premier dépôt.
    de_base = {generate.NOM_00, generate.NOM_01, generate.NOM_02, generate.NOM_05}
    for nom in sorted(de_base | set(etat.get("livres") or {}) | set(echecs) - {generate.NOM_PAPIER}):
        chemin = generate.SORTIE / nom
        numero, titre, quoi = TITRES.get(nom, (nom[:3].strip(" -"), nom.split(" - ", 1)[-1].rsplit(".", 1)[0],
                                               "Guide officiel, copié sans modification."))
        sortie.append({
            "fichier": nom, "numero": numero, "titre": titre, "quoi": quoi,
            "present": chemin.exists(), "poids": chemin.stat().st_size if chemin.exists() else 0,
            "fabrique_le": (registre.get(nom) or {}).get("date"),
            "echec": echecs.get(nom), "va_disparaitre": nom in disparitions,
            "chiffre": nom == generate.NOM_05,
            # Pourquoi le livre des papiers n'existe pas encore, dit en clair
            "attente": None if chemin.exists() or nom != generate.NOM_05 else (
                "Aucun papier déposé : dépose-les ici, puis « Fabriquer »." if not papiers.sources(DATA / "papiers")
                else "Le mot de passe des papiers est absent de la stack (KIT_PAPIERS_PASSWORD) : le livre ne peut pas être chiffré."
                if not cfg.papiers_password else "Papiers déposés : clique « Fabriquer » pour créer le livre chiffré."),
        })
    papier = generate.SORTIE_PAPIER / generate.NOM_PAPIER
    sortie.append({
        "fichier": generate.NOM_PAPIER, "numero": "A4", "titre": "Version papier",
        "quoi": "Lisez-moi, procédures et contacts, à imprimer. Les papiers n'y sont pas.",
        "present": papier.exists(), "poids": papier.stat().st_size if papier.exists() else 0,
        "fabrique_le": _iso_fichier(papier), "echec": echecs.get(generate.NOM_PAPIER),
        "va_disparaitre": False, "chiffre": False, "papier": True,
    })
    return sortie


def chemin_livre(nom: str) -> Path | None:
    """Le fichier fabriqué qui porte ce nom, et rien d'autre (pas de chemin fourni par l'appelant)."""
    if nom == generate.NOM_PAPIER:
        p = generate.SORTIE_PAPIER / generate.NOM_PAPIER
        return p if p.is_file() else None
    for p in generate.SORTIE.iterdir() if generate.SORTIE.exists() else []:
        if p.is_file() and p.name == nom and not p.name.startswith(".") and p.name != "manifest.json":
            return p
    return None


# ------------------------------------------------------------------ à traiter

def changements_papier(cfg: Config, etat: dict) -> list[str] | None:
    """Ce qui a changé depuis la dernière impression confirmée. None : jamais imprimé."""
    ancien = etat.get("papier_instantane")
    if not ancien:
        return None
    actuel = generate.instantane_papier(cfg)
    change = [n for n in actuel if n in ancien and actuel[n] != ancien[n]]
    change += [f"{n} (nouveau)" for n in actuel if n not in ancien]
    change += [f"{n} (retiré)" for n in ancien if n not in actuel]
    return change


def essai(cfg: Config, etat: dict) -> dict:
    dernier = etat.get("essai") or {}
    jours = _jours_depuis(dernier.get("le"))
    change = bool(dernier.get("le")) and dernier.get("mot_de_passe") != empreinte_mot_de_passe(cfg.papiers_password)
    return {"le": dernier.get("le"), "jours": jours, "points": POINTS_ESSAI,
            "mot_de_passe_change": change,
            "a_faire": jours is None or jours >= ESSAI_JOURS or change}


def tuiles(cfg: Config) -> dict:
    etat = status.read()
    modifie = bool(etat.get("version_nas")) and etat.get("sources") != generate.sha_sources(cfg)

    completer = [{"ou": "texte", "nom": t["nom"], "titre": t["titre"], "nombre": t["a_completer"]}
                 for t in textes() if t["a_completer"]]
    verifier = []
    for cat in numeros():
        for n in cat["numeros"]:
            if n["a_completer"]:
                completer.append({"ou": "numero", "nom": n["nom"], "titre": cat["nom"], "nombre": 1})
            if n["a_verifier"]:
                verifier.append({"nom": n["nom"], "numero": n["numero"], "categorie": cat["nom"], "note": n["note"]})
    guides_manquants = [g for g in guides() if g["manques"]]

    controle = etat.get("controle") or {}
    erreurs = [f"{e['livre']} : {e['raison']}" for e in controle.get("echecs", [])]
    if etat.get("derniere_erreur"):
        erreurs.append(str(etat["derniere_erreur"]))

    vu = _jours_depuis(etat.get("kindle_vu_le"))
    recus = _jours_depuis(_iso_fichier(DATA / "config" / cfg.contacts_vcf))
    silence = []
    if cfg.kindle.host and not etat.get("kindle_joignable") and vu is not None and vu >= LISEUSE_JOURS:
        silence.append(f"La liseuse n'a pas été vue depuis {vu} jours : elle est peut-être déchargée.")
    if recus is None:
        silence.append("Aucun contact reçu : envoie le groupe Urgence depuis carnet.")
    elif recus >= CONTACTS_JOURS:
        silence.append(f"Les contacts datent de {recus} jours : renvoie-les depuis carnet.")

    # Les avertissements du générateur déjà couverts par une tuile ne sont pas répétés
    autres = [a for a in etat.get("avertissements") or [] if not a.startswith("Guide «") and "Contacts :" not in a]

    es = essai(cfg, etat)
    papier = {"a_imprimer": bool(etat.get("papier_a_imprimer")), "changements": changements_papier(cfg, etat)}
    liste = {
        "erreur": {"nombre": len(erreurs), "lignes": erreurs},
        "disparition": {"nombre": len(etat.get("disparitions") or []), "livres": etat.get("disparitions") or []},
        "modifie": {"nombre": 1 if modifie else 0},
        "liseuse": {"nombre": 0 if etat.get("a_jour") else 1, "joignable": bool(etat.get("kindle_joignable")),
                    "reglee": bool(cfg.kindle.host)},
        "papier": {"nombre": 1 if papier["a_imprimer"] else 0, **papier},
        "essai": {"nombre": 1 if es["a_faire"] else 0, **es},
        "completer": {"nombre": sum(x["nombre"] for x in completer), "lignes": completer},
        "verifier": {"nombre": len(verifier), "lignes": verifier},
        "guides": {"nombre": len(guides_manquants), "lignes": guides_manquants},
        "silence": {"nombre": len(silence), "lignes": silence},
        "avertissement": {"nombre": len(autres), "lignes": autres},
    }
    total = sum(t["nombre"] for t in liste.values())
    if erreurs:
        phrase = "Le kit a un problème : regarde la tuile « Erreur »."
    elif not etat.get("version_nas"):
        phrase = "Le kit n'a pas encore été fabriqué."
    elif etat.get("a_jour") and not modifie:
        phrase = "Le kit est à jour sur la liseuse."
    elif modifie:
        phrase = "Des sources ont changé : le kit est à refabriquer, puis à livrer."
    else:
        phrase = "Le kit du NAS est plus récent que celui de la liseuse."
    if es["le"]:
        phrase += f" Dernier essai en vrai : il y a {es['jours']} jour(s)." if es["jours"] else " Dernier essai en vrai : aujourd'hui."
    else:
        phrase += " Il n'a jamais été essayé en vrai."
    return {"phrase": phrase, "total": total, "tuiles": liste,
            "derniere_generation": etat.get("derniere_generation"),
            "derniere_livraison": etat.get("derniere_livraison")}


def nombre_a_traiter(cfg: Config) -> int:
    try:
        return tuiles(cfg)["total"]
    except Exception:  # noqa: BLE001 — /status ne doit jamais tomber pour un compteur
        return 0


# ------------------------------------------------------------------ connexion

def connexions(cfg: Config, cle_publique: str) -> dict:
    etat = status.read()
    vcf = DATA / "config" / cfg.contacts_vcf
    return {
        "liseuse": {
            "reglee": bool(cfg.kindle.host), "joignable": bool(etat.get("kindle_joignable")),
            "vue_le": etat.get("kindle_vu_le"), "a_jour": bool(etat.get("a_jour")),
            "derniere_livraison": etat.get("derniere_livraison"),
            "verification": etat.get("derniere_verification"),
            "adresse": f"{cfg.kindle.host}:{cfg.kindle.port}" if cfg.kindle.host else "",
            "dossier": cfg.kindle.dossier, "cle_publique": cle_publique,
        },
        "carnet": {
            "present": vcf.exists(), "recus_le": _iso_fichier(vcf),
            "nombre": len(contacts.lire_vcf(vcf)), "url": config.carnet_url() or None,
        },
        "home_assistant": {
            "jeton_regle": bool(os.environ.get("API_TOKEN", "")),
            "dernier_appel": etat.get("dernier_appel_jeton"),
            "adresses": ["/status", "/generer", "/synchroniser", "/papier/imprime"],
        },
    }


def reglages(cfg: Config) -> dict:
    return {"titre_foyer": cfg.titre_foyer,
            "liseuse": {"host": cfg.kindle.host, "port": cfg.kindle.port, "user": cfg.kindle.user,
                        "dossier": cfg.kindle.dossier},
            "scrutation_secondes": cfg.scrutation_secondes,
            "mot_de_passe_papiers": bool(cfg.papiers_password)}
