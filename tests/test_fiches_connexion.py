"""Fiches « Connexion » communes (contrat 3, socle 0.10.0) : forme de /api/maison/services, accès par session ou
ANNEAU_CLE seulement (jamais MAISON_JETON), « Vérifier » d'un service pas relié n'essaie rien, copies non retouchées
du module commun et de l'interface commune."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main, maison
from app.sauvegarde import APPLI
from tests.conftest import MDP, brancher_liseuse

RACINE = Path(__file__).resolve().parent.parent
CLE = "cle-anneau-de-test-1234567890"
IDS = ["liseuse", "carnet", "home-assistant"]
CHAMPS = {"id", "nom", "genre", "cible", "etat", "lit", "ecrit", "reglage", "detail", "verifie_le", "guide",
          "derniere_ecriture", "gestes"}


@pytest.fixture()
def client(jeu, monkeypatch):
    for v in ("MAISON_JETON", "MAISON_JETON_ANCIEN", "ANNEAU_CLE", "MAISON_LECTURE_SEULE", "KIT_LECTURE_SEULE"):
        monkeypatch.delenv(v, raising=False)
    main.ETAT.clear()
    main.SERVICES._dernier.clear()               # pas d'essai d'un autre test (limite de 30 s)
    fausse = brancher_liseuse(monkeypatch)
    with TestClient(main.app) as c:
        c.liseuse = fausse
        yield c
    main.ETAT.clear()
    main.SERVICES._dernier.clear()


def connecter(client):
    assert client.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200


def test_forme_du_contrat_3(client):
    connecter(client)
    r = client.get("/api/maison/services")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    corps = r.json()
    assert corps["contrat"] == 3 and corps["appli"] == APPLI and corps["simule"] is False
    assert [s["id"] for s in corps["services"]] == IDS
    for s in corps["services"]:
        assert set(s) == CHAMPS and s["lit"] and s["ecrit"] and s["etat"] in maison.ETATS_SERVICE
        assert len(s["gestes"]) <= 1
        if s["etat"] == "pas_relie":
            assert s["reglage"]


def test_acces_session_ou_cle_anneau(client, monkeypatch):
    assert client.get("/api/maison/services").status_code == 401
    monkeypatch.setenv("MAISON_JETON", "jeton-commun-de-test-12345")
    entete = {"Authorization": "Bearer jeton-commun-de-test-12345"}
    assert client.get("/api/maison/services", headers=entete).status_code == 401
    monkeypatch.setenv("ANNEAU_CLE", CLE)
    assert client.get("/api/maison/services", headers={"Authorization": f"Bearer {CLE}"}).status_code == 200
    assert client.get("/api/maison/services", headers={"Authorization": "Bearer mauvaise"}).status_code == 401


def test_verifier_inconnu_et_pas_relie(client):
    connecter(client)
    assert client.post("/api/maison/services/inconnu/verifier").status_code == 404
    for s in client.get("/api/maison/services").json()["services"]:
        if s["etat"] == "pas_relie":
            apres = client.post(f"/api/maison/services/{s['id']}/verifier").json()
            assert apres["etat"] == "pas_relie" and apres["verifie_le"] is None


def test_copies_communes_non_retouchees():
    assert maison.CONTRAT == 3 and maison.VERSION_SOCLE == "0.11.1"
    assert maison.empreinte_calculee() == maison.empreinte_ecrite()
    for nom in maison.FICHIERS_INTERFACE:
        ecrite, calculee = maison.empreinte_interface(RACINE / "frontend" / "src" / "lib" / "services" / nom)
        assert ecrite and ecrite == calculee, nom


# ---------------------------------------------------------------- propre au kit (2.7.0)

def test_liseuse_verifier_compare_sans_rien_ecrire(client, jeu, monkeypatch):
    """« Vérifier » de la fiche Liseuse : la comparaison de toujours, rien d'écrit sur la liseuse, même en lecture
    seule ; le geste « Livrer » est porté par la fiche, avec son guide."""
    connecter(client)
    client.post("/api/livrer")
    main.SERVICES._dernier.clear()
    monkeypatch.setenv("KIT_LECTURE_SEULE", "oui")
    avant = {p.name: p.read_bytes() for p in (jeu / "liseuse").iterdir()}
    n = len(client.liseuse.commandes)
    fiche = client.post("/api/maison/services/liseuse/verifier").json()
    assert fiche["etat"] == "repond" and "la liseuse a bien le kit du NAS" in fiche["detail"]
    assert fiche["gestes"] == [{"id": "livrer", "nom": "Livrer"}] and fiche["derniere_ecriture"]
    assert all(not any(m in c for m in ("cat >", "mv ", "rm ", "mkdir")) for c in client.liseuse.commandes[n:])
    assert {p.name: p.read_bytes() for p in (jeu / "liseuse").iterdir()} == avant
    guide = fiche["guide"]
    assert guide["allumer"] and guide["pannes"] and guide["une_fois"] and guide["reglages"]
    assert any(u["commande"].startswith("ssh-ed25519 ") for u in guide["une_fois"])
    assert "papiers-essai" not in str(fiche) and "root" not in str(guide["reglages"])


def test_liseuse_qui_ne_repond_pas_et_pas_reglee(client, jeu):
    connecter(client)
    client.liseuse.joignable = False
    fiche = client.post("/api/maison/services/liseuse/verifier").json()
    assert fiche["etat"] == "ne_repond_pas" and "ne répond pas" in fiche["detail"]
    cfg = jeu / "data" / "config" / "config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace('host: "127.0.0.1"', 'host: ""'), encoding="utf-8")
    fiche = next(s for s in client.get("/api/maison/services").json()["services"] if s["id"] == "liseuse")
    assert fiche["etat"] == "pas_relie" and "Réglages" in fiche["reglage"]


def test_livrer_sert_d_essai_et_carnet_ha(client):
    connecter(client)
    client.post("/api/livrer")
    fiches = {s["id"]: s for s in client.get("/api/maison/services").json()["services"]}
    assert fiches["liseuse"]["etat"] == "repond" and fiches["liseuse"]["detail"] == "Livraison faite et vérifiée."
    assert fiches["carnet"]["genre"] == "maison" and fiches["carnet"]["cible"] == "carnet"
    carnet = client.post("/api/maison/services/carnet/verifier").json()
    assert carnet["etat"] == "repond" and carnet["detail"].startswith("2 contact(s) reçus le ")
    ha = client.post("/api/maison/services/home-assistant/verifier").json()
    assert ha["etat"] == "repond" and "aucun appel" in ha["detail"]
