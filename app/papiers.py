"""Livre 05 – Papiers : fusion des scans (PDF/JPG/PNG) puis chiffrement AES-256 (qpdf)."""
from __future__ import annotations

import os
import secrets
import subprocess
import tempfile
from pathlib import Path

import img2pdf

EXT_IMG = {".jpg", ".jpeg", ".png"}
EXT_PDF = {".pdf"}
A4 = (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))


def sources(dossier: Path) -> list[Path]:
    if not dossier.exists():
        return []
    fichiers = [
        p for p in dossier.rglob("*")
        if p.is_file() and p.suffix.lower() in EXT_IMG | EXT_PDF and not p.name.startswith(".")
    ]
    # Ordre stable : chemin relatif (préfixer les fichiers par 01-, 02-… pour choisir l'ordre)
    return sorted(fichiers, key=lambda p: str(p.relative_to(dossier)).lower())


def construire(dossier: Path, sortie: Path, mot_de_passe: str) -> int:
    """Crée le PDF chiffré. Retourne le nombre de documents fusionnés (0 = rien produit)."""
    docs = sources(dossier)
    if not docs:
        return 0
    if not mot_de_passe:
        raise RuntimeError("PAPIERS_PASSWORD absent : le livre 05 n'est pas généré en clair.")
    layout = img2pdf.get_layout_fun(A4, fit=img2pdf.FitMode.into)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pdfs = []
        for i, doc in enumerate(docs):
            if doc.suffix.lower() in EXT_IMG:
                cible = tmp / f"{i:03d}.pdf"
                cible.write_bytes(img2pdf.convert(str(doc), layout_fun=layout))
                pdfs.append(cible)
            else:
                pdfs.append(doc)
        fusion = tmp / "fusion.pdf"
        subprocess.run(
            ["qpdf", "--empty", "--pages", *map(str, pdfs), "--", str(fusion)],
            check=True, capture_output=True,
        )
        # Mot de passe passé par fichier d'arguments (mode 600) pour ne pas
        # apparaître dans la liste des processus.
        owner = secrets.token_urlsafe(24)
        args = tmp / "args"
        fd = os.open(args, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join([
                "--encrypt", mot_de_passe, owner, "256", "--", str(fusion), str(sortie),
            ]))
        subprocess.run(["qpdf", f"@{args}"], check=True, capture_output=True)
    return len(docs)
