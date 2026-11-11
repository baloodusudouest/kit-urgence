"""Contrôle après fabrication (2.0.0, avis du conseil) : la machine rouvre ce qu'elle vient de fabriquer.

Égalité d'empreintes ne veut pas dire « lisible ». Avant qu'un livre remplace l'ancien :
- un EPUB doit s'ouvrir, être complet, et contenir du texte ;
- le livre des papiers doit exiger un mot de passe, et s'ouvrir avec celui de la stack ;
- un PDF doit commencer comme un PDF.
Un livre qui échoue ne remplace jamais le dernier bon."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


class Echec(Exception):
    """Le livre fabriqué n'est pas utilisable."""


def epub(chemin: Path) -> None:
    try:
        with zipfile.ZipFile(chemin) as z:
            if z.testzip() is not None:
                raise Echec("fichier abîmé")
            noms = z.namelist()
            if "mimetype" not in noms or z.read("mimetype").strip() != b"application/epub+zip":
                raise Echec("ce n'est pas un livre EPUB")
            pages = [n for n in noms if n.endswith((".xhtml", ".html")) and "nav" not in Path(n).name]
            texte = " ".join(re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", errors="replace")) for n in pages)
    except zipfile.BadZipFile as exc:
        raise Echec("fichier illisible") from exc
    if len(texte.split()) < 20:
        raise Echec("livre vide")


def pdf(chemin: Path) -> None:
    with chemin.open("rb") as f:
        if f.read(5) != b"%PDF-":
            raise Echec("ce n'est pas un PDF")
    if chemin.stat().st_size < 200:
        raise Echec("PDF vide")


def papiers(chemin: Path, mot_de_passe: str, attendus: int | None = None) -> None:
    """Le livre doit refuser de s'ouvrir sans mot de passe, et s'ouvrir avec le bon."""
    pdf(chemin)
    if subprocess.run(["qpdf", "--requires-password", str(chemin)], capture_output=True).returncode != 0:
        raise Echec("le livre des papiers s'ouvre sans mot de passe")
    with tempfile.TemporaryDirectory() as tmp:
        secret = Path(tmp) / "mdp"
        fd = os.open(secret, os.O_WRONLY | os.O_CREAT, 0o600)      # jamais dans la liste des processus
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(mot_de_passe)
        r = subprocess.run(["qpdf", f"--password-file={secret}", "--show-npages", str(chemin)],
                           capture_output=True, text=True)
    if r.returncode != 0:
        raise Echec("le livre des papiers ne s'ouvre pas avec le mot de passe de la stack")
    if attendus is not None and r.stdout.strip().isdigit() and int(r.stdout.strip()) < attendus:
        raise Echec("il manque des pages dans le livre des papiers")


def verifier(nom: str, chemin: Path, mot_de_passe: str = "", est_papiers: bool = False,
             pages: int | None = None) -> None:
    if not chemin.exists() or chemin.stat().st_size == 0:
        raise Echec("rien n'a été fabriqué")
    if est_papiers:
        papiers(chemin, mot_de_passe, pages)
    elif nom.lower().endswith(".epub"):
        epub(chemin)
    elif nom.lower().endswith(".pdf"):
        pdf(chemin)
