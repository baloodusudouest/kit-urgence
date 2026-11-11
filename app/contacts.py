"""Livre 02 – Contacts : export .vcf iCloud + numéros publics (YAML) -> Markdown."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import vobject
import yaml

TYPES_TEL = {
    "CELL": "mobile", "HOME": "domicile", "WORK": "travail",
    "MAIN": "principal", "IPHONE": "mobile", "VOICE": "",
}


def _tel_label(tel) -> str:
    types = [t.upper() for t in tel.params.get("TYPE", [])]
    labels = [TYPES_TEL.get(t, "") for t in types]
    labels = [lbl for lbl in labels if lbl]
    return labels[0] if labels else ""


log = logging.getLogger(__name__)

# Ligne vCard valide : BEGIN/END ou « [groupe.]NOM[;paramètres]:valeur »
_LIGNE = re.compile(r"^(?:[A-Za-z0-9-]+\.)?[A-Za-z0-9-]+(?:;[^:]*)?:", re.ASCII)
# Données de prononciation de Siri : JSON sur plusieurs lignes, illisible pour vobject et inutile au kit
_JETEES = ("X-ADDRESSBOOKSERVER-PHONEME-DATA",)


def _cartes_propres(texte: str) -> list[str]:
    """Découpe le fichier en cartes et retire les lignes qu'iCloud écrit hors norme."""
    lignes: list[str] = []
    for brute in texte.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if brute[:1] in (" ", "\t") and lignes:      # ligne repliée : suite de la précédente
            lignes[-1] += brute[1:]
        elif brute.strip():
            lignes.append(brute)
    cartes, carte = [], None
    for l in lignes:
        haut = l.upper()
        if haut.startswith("BEGIN:VCARD"):
            carte = [l]
        elif carte is not None and haut.startswith("END:VCARD"):
            carte.append(l)
            cartes.append("\r\n".join(carte) + "\r\n")
            carte = None
        elif carte is not None and _LIGNE.match(l) and not haut.split(";")[0].split(":")[0].split(".")[-1] in _JETEES:
            carte.append(l)
    return cartes


def lire_vcf(path: Path) -> list[dict]:
    """Retourne une liste de contacts {nom, organisation, tels, emails, adresses, note}."""
    if not path.exists():
        return []
    contacts = []
    texte = path.read_text(encoding="utf-8", errors="replace")
    for bloc in _cartes_propres(texte):
        try:
            card = vobject.readOne(bloc, ignoreUnreadable=True)
        except Exception as exc:  # noqa: BLE001 — une carte illisible n'empêche pas les autres
            log.warning("Contact ignoré (carte illisible) : %s", str(exc)[:120])
            continue
        nom = card.fn.value.strip() if hasattr(card, "fn") else ""
        org = ""
        if hasattr(card, "org"):
            org = " ".join(v for v in card.org.value if v).strip()
        tels = []
        for tel in card.contents.get("tel", []):
            lbl = _tel_label(tel)
            tels.append(f"{tel.value.strip()}" + (f" ({lbl})" if lbl else ""))
        emails = [e.value.strip() for e in card.contents.get("email", [])]
        adresses = []
        for adr in card.contents.get("adr", []):
            a = adr.value
            morceaux = [a.street, f"{a.code} {a.city}".strip()]
            adresses.append(", ".join(m.strip() for m in morceaux if m and m.strip()))
        note = card.note.value.strip() if hasattr(card, "note") else ""
        uid = card.uid.value.strip() if hasattr(card, "uid") else ""
        contacts.append({
            "uid": uid, "nom": nom or org or "(sans nom)", "organisation": org,
            "tels": tels, "emails": emails, "adresses": adresses, "note": note,
        })
    return sorted(contacts, key=lambda c: c["nom"].lower())


def lire_publics(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("categories", [])


def markdown(vcf: Path, publics: Path) -> str:
    lignes = ["# Contacts", ""]
    cats = lire_publics(publics)
    if cats:
        lignes += ["## Numéros d'urgence et services", ""]
        for cat in cats:
            lignes += [f"### {cat.get('nom', '')}", ""]
            for n in cat.get("numeros", []):
                ligne = f"- **{n.get('nom', '')}** : {n.get('numero', '')}"
                if n.get("note"):
                    ligne += f" — {n['note']}"
                lignes.append(ligne)
            lignes.append("")
    contacts = lire_vcf(vcf)
    lignes += ["## Proches et artisans", ""]
    if not contacts:
        lignes += [
            "*Aucun contact : déposer l'export du groupe iCloud « Urgence » "
            f"dans config/{vcf.name}.*", "",
        ]
    for c in contacts:
        lignes += [f"### {c['nom']}", ""]
        if c["organisation"] and c["organisation"] != c["nom"]:
            lignes.append(f"- {c['organisation']}")
        lignes += [f"- Tél. : **{t}**" for t in c["tels"]]
        lignes += [f"- Courriel : {e}" for e in c["emails"]]
        lignes += [f"- Adresse : {a}" for a in c["adresses"]]
        if c["note"]:
            lignes.append(f"- Note : {c['note']}")
        lignes.append("")
    return "\n".join(lignes)
