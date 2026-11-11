"""Ce que le kit 1.0.1 fabrique et livre, figé avant d'y toucher (dossier 2.0, étape 1).

Chaque livre porte sa date en page de garde : on compare donc le texte et la structure, pas une empreinte."""
from __future__ import annotations

import json
import subprocess
import zipfile

from app import config, generate, status, sync

from .conftest import MDP_PAPIERS


def texte_epub(chemin) -> str:
    with zipfile.ZipFile(chemin) as z:
        return "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith((".xhtml", ".html")))


def test_la_generation_fabrique_les_livres_attendus(jeu):
    etat = generate.generer(config.load())
    sortie = generate.SORTIE
    assert sorted(etat["livres"]) == [generate.NOM_00, generate.NOM_01, generate.NOM_02, generate.NOM_05]
    assert "Maison des Tilleuls" in texte_epub(sortie / generate.NOM_00)
    procedures = texte_epub(sortie / generate.NOM_01)
    assert "lectricit" in procedures and "Maison des Tilleuls" in procedures
    contacts = texte_epub(sortie / generate.NOM_02)
    assert "Plomberie du Coteau" in contacts and "05 55 00 00 01" in contacts
    assert "Camille Voisin" in contacts and "06 00 00 00 02" in contacts
    assert "112" in contacts                                   # numéros publics
    manifest = json.loads((sortie / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["livres"] == etat["livres"] and manifest["version"] == etat["version_nas"]
    assert sync.verifier_local()
    papier = generate.SORTIE_PAPIER / generate.NOM_PAPIER
    assert papier.read_bytes()[:5] == b"%PDF-"
    assert etat["papier_a_imprimer"] is True and etat["derniere_erreur"] is None


def test_le_livre_des_papiers_est_chiffre(jeu):
    generate.generer(config.load())
    livre = generate.SORTIE / generate.NOM_05
    # qpdf --requires-password : 0 = mot de passe exigé
    assert subprocess.run(["qpdf", "--requires-password", str(livre)]).returncode == 0
    ok = subprocess.run(["qpdf", f"--password={MDP_PAPIERS}", "--check", str(livre)], capture_output=True)
    assert ok.returncode == 0
    faux = subprocess.run(["qpdf", "--password=autre", "--check", str(livre)], capture_output=True)
    assert faux.returncode != 0


def test_seul_le_livre_touche_est_refait(jeu):
    cfg = config.load()
    avant = generate.generer(cfg)["livres"]
    assert generate.generer(cfg)["livres"] == avant            # rien n'a changé : rien n'est refait
    texte = jeu / "data" / "procedures" / "10-electricite.md"
    texte.write_text(texte.read_text(encoding="utf-8") + "\n\nPhrase ajoutée pour l'essai.\n", encoding="utf-8")
    apres = generate.generer(cfg)["livres"]
    changes = {n for n in avant if avant[n] != apres[n]}
    assert changes == {generate.NOM_01}
    assert "Phrase ajoutée" in texte_epub(generate.SORTIE / generate.NOM_01)


def test_sans_mot_de_passe_les_papiers_ne_sortent_pas_en_clair(jeu, monkeypatch):
    monkeypatch.setenv("PAPIERS_PASSWORD", "")
    etat = generate.generer(config.load())
    assert generate.NOM_05 not in etat["livres"]
    assert any("PAPIERS_PASSWORD" in a for a in etat["avertissements"])


def test_la_livraison_depose_et_verifie(liseuse, jeu):
    cfg = config.load()
    generate.generer(cfg)
    etat = sync.livrer(cfg)
    dossier = jeu / "liseuse"
    assert etat["a_jour"] is True and etat["derniere_verification"] == "sha256"
    deposes = sorted(p.name for p in dossier.iterdir())
    assert deposes == sorted([*etat["livres"], "manifest.json"])
    assert sorted(etat["derniers_envoyes"]) == sorted(etat["livres"])
    # Deuxième passage : rien à renvoyer
    assert sync.livrer(cfg)["derniers_envoyes"] == []
    assert status.read()["version_kindle"] == status.read()["version_nas"]
