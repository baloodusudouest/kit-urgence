"""La 2.1.0 : ce que l'écran écrit dans les sources. Chaque écriture garde l'ancien, n'écrase rien,
ne sort jamais du dossier prévu, et se refuse deux fois en lecture seule."""
from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

from app import config, ecrits, generate, main

from .conftest import MDP, PNG, brancher_liseuse
from .test_existant import texte_epub

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n" \
      b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
GUIDE = {"titre": "Guide inventé", "editeur": "Préfecture inventée", "url": "https://exemple.gouv.test/guide"}


@pytest.fixture()
def ecran(jeu, monkeypatch):
    main.ETAT.clear()
    fausse = brancher_liseuse(monkeypatch)
    with TestClient(main.app) as c:
        c.liseuse = fausse
        assert c.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200
        yield c
    main.ETAT.clear()


def noms(d):
    return [p["nom"] for p in d["papiers"]]


# ---------------------------------------------------------------- portes

def test_les_ecritures_sont_fermees_sans_session(jeu, monkeypatch):
    main.ETAT.clear()
    brancher_liseuse(monkeypatch)
    with TestClient(main.app) as c:
        assert c.put("/api/textes/10-electricite.md", json={"contenu": "x"}).status_code == 401
        assert c.put("/api/papiers", params={"nom": "a.png"}, content=PNG).status_code == 401
        assert c.put("/api/reglages", json={}).status_code == 401
        assert c.post("/api/papiers/effacer", json={"id": "x"}).status_code == 401
        assert c.delete("/api/guides/0").status_code == 401
        assert c.put("/api/guides/fichier", params={"nom": "g.pdf", **GUIDE}, content=PDF).status_code == 401
    main.ETAT.clear()


def test_lecture_seule_refuse_toutes_les_ecritures_deux_fois(ecran, jeu, monkeypatch):
    avant = {p: p.read_bytes() for p in (jeu / "data").rglob("*") if p.is_file() and "output" not in p.parts}
    monkeypatch.setenv("KIT_LECTURE_SEULE", "1")
    appels = [
        ecran.put("/api/textes/10-electricite.md", json={"contenu": "# Autre\n"}),
        ecran.post("/api/textes", json={"titre": "Nouveau", "numero": 60}),
        ecran.delete("/api/textes/20-eau.md"),
        ecran.put("/api/numeros/0/0", json={"nom": "x", "numero": "1"}),
        ecran.post("/api/numeros/1/1/verifie"),
        ecran.put("/api/papiers", params={"nom": "b.png"}, content=PNG),
        ecran.post("/api/papiers/retirer", json={"nom": "01-carte.png"}),
        ecran.post("/api/papiers/ordre", json={"noms": ["01-carte.png"]}),
        ecran.put("/api/guides/fichier", params={"nom": "g.pdf", **GUIDE}, content=PDF),
        ecran.delete("/api/guides/0"),
        ecran.put("/api/reglages", json={"titre_foyer": "x", "liseuse": {"dossier": "/a/b"}}),
    ]
    assert [r.status_code for r in appels] == [409] * len(appels)
    with pytest.raises(Exception, match="lecture seule"):                    # et au plus près du fichier
        ecrits.enregistrer_texte("10-electricite.md", "# Autre\n")
    with pytest.raises(Exception, match="lecture seule"):
        ecrits.retirer_papier("01-carte.png")
    with pytest.raises(Exception, match="lecture seule"):
        ecrits.deposer_papier("b.png", PNG)
    apres = {p: p.read_bytes() for p in (jeu / "data").rglob("*") if p.is_file() and "output" not in p.parts}
    assert apres == avant
    assert not any("modifié" in l["quoi"] or "déposé" in l["quoi"] for l in ecran.get("/api/reglages").json()["journal"])


# ---------------------------------------------------------------- textes

def test_enregistrer_un_texte_garde_l_ancien_et_ne_fabrique_pas(ecran, jeu):
    avant = (generate.SORTIE / generate.NOM_01).read_bytes()
    origine = ecran.get("/api/textes/10-electricite.md").json()
    assert origine["versions"] == []
    r = ecran.put("/api/textes/10-electricite.md", json={"contenu": origine["contenu"] + "\nLe disjoncteur est dans le cellier.\n"})
    assert r.status_code == 200 and len(r.json()["versions"]) == 1
    assert (generate.SORTIE / generate.NOM_01).read_bytes() == avant           # enregistrer ne fabrique pas
    etat = ecran.get("/api/etat").json()
    assert etat["tuiles"]["modifie"]["nombre"] == 1
    ecran.post("/api/generer")
    assert "dans le cellier" in texte_epub(generate.SORTIE / generate.NOM_01)
    # Les versions ne sont pas rangées là où le générateur regarde : le kit n'est pas « modifié » pour autant
    assert ecran.get("/api/etat").json()["tuiles"]["modifie"]["nombre"] == 0
    assert ecran.put("/api/textes/10-electricite.md", json={"contenu": "   "}).status_code == 422
    assert ecran.put("/api/textes/absent.md", json={"contenu": "x"}).status_code == 404


def test_revenir_a_une_version_et_dix_versions_au_plus(ecran):
    origine = ecran.get("/api/textes/20-eau.md").json()["contenu"]
    for i in range(13):
        ecran.put("/api/textes/20-eau.md", json={"contenu": f"# Eau\n\nVersion {i}\n"})
    t = ecran.get("/api/textes/20-eau.md").json()
    assert len(t["versions"]) == 10 and t["contenu"] == "# Eau\n\nVersion 12\n"
    ancienne = t["versions"][3]["id"]
    contenu = ecran.get(f"/api/textes/20-eau.md/versions/{ancienne}").json()["contenu"]
    assert contenu.startswith("# Eau\n\nVersion ") and contenu != origine
    r = ecran.post("/api/textes/20-eau.md/revenir", json={"version": ancienne}).json()
    assert r["contenu"] == contenu
    assert any("Version 12" in ecran.get(f"/api/textes/20-eau.md/versions/{v['id']}").json()["contenu"] for v in r["versions"])
    assert ecran.post("/api/textes/20-eau.md/revenir", json={"version": "../../config"}).status_code == 404


def test_creer_et_supprimer_un_texte(ecran, jeu):
    r = ecran.post("/api/textes", json={"titre": "Poêle à bois", "numero": 35})
    assert r.status_code == 200 and r.json()["nom"] == "35-poele-a-bois.md"
    assert [t["nom"] for t in r.json()["textes"]][3:5] == ["30-chauffage.md", "35-poele-a-bois.md"]
    assert ecran.post("/api/textes", json={"titre": "Poêle à bois", "numero": 35}).status_code == 409
    assert ecran.post("/api/textes", json={"titre": "", "numero": 35}).status_code == 422
    assert ecran.post("/api/textes", json={"titre": "X", "numero": 0}).status_code == 422
    assert ecran.delete("/api/textes/00-lisez-moi.md").status_code == 422   # la première page ne se supprime pas
    assert ecran.delete("/api/textes/35-poele-a-bois.md").status_code == 200
    assert not (jeu / "data" / "procedures" / "35-poele-a-bois.md").exists()
    assert len(list((jeu / "data" / "versions" / "procedures" / "35-poele-a-bois.md").iterdir())) == 1


# ---------------------------------------------------------------- numéros publics

def test_corriger_et_verifier_un_numero(ecran, jeu):
    d = ecran.get("/api/livres").json()
    reseaux = d["numeros"][1]
    assert reseaux["numeros"][0]["a_completer"] and reseaux["numeros"][1]["a_verifier"]
    assert ecran.post("/api/numeros/1/0/verifie").status_code == 422           # encore à compléter
    d = ecran.put("/api/numeros/1/0", json={"nom": "Dépannage électricité", "numero": "09 72 67 50 00"}).json()
    assert d["numeros"][1]["numeros"][0]["numero"] == "09 72 67 50 00" and not d["numeros"][1]["numeros"][0]["a_completer"]
    d = ecran.post("/api/numeros/1/1/verifie").json()
    n = d["numeros"][1]["numeros"][1]
    assert n["verifie_le"] and not n["a_verifier"] and "vérifier" not in n["note"]
    # Changer le numéro lui retire son « vérifié »
    d = ecran.put("/api/numeros/1/1", json={"nom": n["nom"], "numero": "0 800 00 00 00"}).json()
    assert d["numeros"][1]["numeros"][1]["verifie_le"] is None
    brut = (jeu / "data" / "config" / "numeros-publics.yaml").read_text(encoding="utf-8")
    assert "Dépannage électricité" in brut and yaml.safe_load(brut)["categories"][0]["numeros"][0]["numero"] == "112"
    assert list((jeu / "data" / "versions" / "config" / "numeros-publics.yaml").iterdir())   # l'original est gardé
    ecran.post("/api/generer")
    assert "09 72 67 50 00" in texte_epub(generate.SORTIE / generate.NOM_02)
    assert ecran.put("/api/numeros/9/0", json={"nom": "x", "numero": "1"}).status_code == 404
    assert ecran.put("/api/numeros/1/0", json={"nom": "", "numero": "1"}).status_code == 422
    assert ecran.post("/api/numeros/2", json={"nom": "Vétérinaire de garde", "numero": "05 55 00 00 09"}).status_code == 200
    avant = len(ecran.get("/api/livres").json()["numeros"][2]["numeros"])
    assert len(ecran.delete(f"/api/numeros/2/{avant - 1}").json()["numeros"][2]["numeros"]) == avant - 1


# ---------------------------------------------------------------- papiers

def test_deposer_un_papier_le_range_a_la_fin_sans_rien_ecraser(ecran, jeu):
    d = ecran.put("/api/papiers", params={"nom": "Passeport été.PDF"}, content=PDF).json()
    assert noms(d) == ["01-carte.png", "02-Passeport-ete.pdf"]
    assert ecran.put("/api/papiers", params={"nom": "note.txt"}, content=b"bonjour").status_code == 422
    assert ecran.put("/api/papiers", params={"nom": "faux.pdf"}, content=PNG).status_code == 422     # contenu ≠ extension
    assert ecran.put("/api/papiers", params={"nom": "vide.png"}, content=b"").status_code == 422
    d = ecran.put("/api/papiers", params={"nom": "../../config/config.png"}, content=PNG).json()
    assert noms(d)[-1] == "03-config.png" and (jeu / "data" / "papiers" / "03-config.png").exists()
    assert "titre_foyer" in (jeu / "data" / "config" / "config.yaml").read_text(encoding="utf-8")
    journal = str(ecran.get("/api/reglages").json()["journal"])
    assert "Un papier déposé" in journal and "Passeport" not in journal           # jamais de nom de papier
    ecran.post("/api/generer")
    assert generate.NOM_05 in ecran.get("/status").json()["livres"] and "Passeport" not in str(ecran.get("/status").json())


def test_papier_trop_lourd(ecran, monkeypatch):
    monkeypatch.setattr(ecrits, "MAX_PAPIER", 1000)
    assert ecran.put("/api/papiers", params={"nom": "gros.pdf"}, content=PDF + b"0" * 2000).status_code == 413


def test_ordre_et_nom_des_papiers(ecran):
    ecran.put("/api/papiers", params={"nom": "permis.png"}, content=PNG)
    ecran.put("/api/papiers", params={"nom": "livret.pdf"}, content=PDF)
    d = ecran.post("/api/papiers/ordre", json={"noms": ["03-livret.pdf", "01-carte.png", "02-permis.png"]}).json()
    assert noms(d) == ["01-livret.pdf", "02-carte.png", "03-permis.png"]
    assert ecran.post("/api/papiers/ordre", json={"noms": ["01-livret.pdf"]}).status_code == 409
    d = ecran.post("/api/papiers/renommer", json={"nom": "02-carte.png", "nouveau": "Carte d'identité"}).json()
    assert noms(d) == ["01-livret.pdf", "02-Carte-d-identite.png", "03-permis.png"]
    assert ecran.post("/api/papiers/renommer", json={"nom": "03-permis.png", "nouveau": "livret"}).status_code == 200
    assert ecran.post("/api/papiers/renommer", json={"nom": "absent.png", "nouveau": "x"}).status_code == 404


def test_un_papier_retire_est_mis_de_cote_et_ne_repart_pas_dans_le_livre(ecran, jeu):
    ecran.put("/api/papiers", params={"nom": "permis.png"}, content=PNG)
    ecran.post("/api/generer")
    d = ecran.post("/api/papiers/retirer", json={"nom": "02-permis.png"}).json()
    assert noms(d) == ["01-carte.png"] and [r["nom"] for r in d["retires"]] == ["02-permis.png"]
    assert (jeu / "data" / "retires" / "papiers").is_dir()
    etat = ecran.post("/api/generer").json()
    assert etat["tuiles"]["erreur"]["nombre"] == 0 and etat["tuiles"]["disparition"]["nombre"] == 0
    # Le livre refait n'a plus qu'une page
    from app import controle
    controle.papiers(generate.SORTIE / generate.NOM_05, "papiers-essai", 1)
    with pytest.raises(controle.Echec):
        controle.papiers(generate.SORTIE / generate.NOM_05, "papiers-essai", 2)
    ident = d["retires"][0]["id"]
    d = ecran.post("/api/papiers/remettre", json={"id": ident}).json()
    assert noms(d) == ["01-carte.png", "02-permis.png"] and d["retires"] == []
    d = ecran.post("/api/papiers/retirer", json={"nom": "02-permis.png"}).json()
    d = ecran.post("/api/papiers/effacer", json={"id": d["retires"][0]["id"]}).json()
    assert d["retires"] == [] and not list((jeu / "data" / "retires" / "papiers").iterdir())
    assert ecran.post("/api/papiers/effacer", json={"id": "../papiers/01-carte.png"}).status_code == 404
    assert (jeu / "data" / "papiers" / "01-carte.png").exists()


def test_retirer_le_dernier_papier_ne_fait_pas_disparaitre_le_livre_sans_un_oui(ecran):
    ecran.post("/api/livrer")
    ecran.post("/api/papiers/retirer", json={"nom": "01-carte.png"})
    etat = ecran.post("/api/generer").json()
    assert etat["tuiles"]["disparition"]["livres"] == [generate.NOM_05]
    assert (generate.SORTIE / generate.NOM_05).exists()


# ---------------------------------------------------------------- guides

def test_un_guide_n_entre_qu_avec_son_editeur_et_son_adresse(ecran, jeu):
    for manque in ("titre", "editeur", "url"):
        fiche = {k: v for k, v in GUIDE.items() if k != manque}
        assert ecran.put("/api/guides/fichier", params={"nom": "g.pdf", **fiche}, content=PDF).status_code == 422, manque
    assert ecran.put("/api/guides/fichier", params={"nom": "g.pdf", **GUIDE, "url": "exemple"}, content=PDF).status_code == 422
    assert not (jeu / "data" / "guides" / "g.pdf").exists()
    d = ecran.put("/api/guides/fichier", params={"nom": "g.pdf", **GUIDE, "date": "2026-01"}, content=PDF).json()
    assert d["guides"][-1] == {**d["guides"][-1], "titre": "Guide inventé", "present": True, "manques": []}
    assert ecran.put("/api/guides/fichier", params={"nom": "g.pdf", **GUIDE}, content=PDF).status_code == 409
    etat = ecran.post("/api/generer").json()
    assert etat["tuiles"]["guides"]["nombre"] == 3                              # les trois du modèle manquent toujours
    assert any(l["numero"].startswith("04") and l["titre"] == "Guide inventé" for l in ecran.get("/api/livres").json()["livres"])


def test_joindre_le_fichier_d_un_guide_declare_puis_le_retirer(ecran, jeu):
    assert ecran.put("/api/guides/0/fichier", content=PNG).status_code == 422   # un PDF est attendu
    d = ecran.put("/api/guides/0/fichier", content=PDF).json()
    assert d["guides"][0]["present"] and (jeu / "data" / "guides" / "tous-responsables.pdf").exists()
    assert ecran.put("/api/guides/0/fichier", content=PDF).status_code == 409
    d = ecran.put("/api/guides/1", json={**GUIDE, "titre": "Titre corrigé"}).json()
    assert d["guides"][1]["titre"] == "Titre corrigé" and d["guides"][1]["fichier"] == "fm-3-05-70-survie-fr.epub"
    assert ecran.put("/api/guides/1", json={"titre": "x"}).status_code == 422
    d = ecran.delete("/api/guides/0").json()
    assert len(d["guides"]) == 2 and not (jeu / "data" / "guides" / "tous-responsables.pdf").exists()
    assert len(list((jeu / "data" / "retires" / "guides").iterdir())) == 1      # le fichier est mis de côté
    assert ecran.delete("/api/guides/7").status_code == 404


# ---------------------------------------------------------------- réglages

def test_reglages(ecran, jeu):
    bon = {"titre_foyer": "Maison du Verger", "scrutation_secondes": 120,
           "liseuse": {"host": "192.0.2.50", "port": 2222, "user": "root", "dossier": "/mnt/us/documents/Urgence"}}
    r = ecran.put("/api/reglages", json=bon).json()
    assert r["titre_foyer"] == "Maison du Verger" and r["liseuse"]["host"] == "192.0.2.50"
    cfg = config.load()
    assert cfg.kindle.dossier == "/mnt/us/documents/Urgence" and cfg.scrutation_secondes == 120
    assert cfg.contacts_vcf == "contacts-urgence.vcf"
    for mauvais in ({"liseuse": {**bon["liseuse"], "dossier": "/"}}, {"liseuse": {**bon["liseuse"], "dossier": "/mnt"}},
                    {"liseuse": {**bon["liseuse"], "dossier": "/mnt/us/../.."}}, {"liseuse": {**bon["liseuse"], "port": 0}},
                    {"liseuse": {**bon["liseuse"], "host": "a b; rm"}}, {"titre_foyer": ""}, {"scrutation_secondes": 2},
                    {"liseuse": {**bon["liseuse"], "dossier": "/mnt/us/documents/Urgence; rm -rf x"}}):
        assert ecran.put("/api/reglages", json={**bon, **mauvais}).status_code == 422, mauvais
    assert ecran.get("/api/etat").json()["tuiles"]["modifie"]["nombre"] == 1    # le nom du foyer est sur chaque page de garde
    assert list((jeu / "data" / "versions" / "config" / "config.yaml").iterdir())
