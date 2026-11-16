"""2.4.0 : variables communes de la maison (module app/maison.py du socle, copié tel quel).

Mot de passe commun, lecture seule de toute la maison, jeton commun accepté en plus d'API_TOKEN sur les
adresses à jeton (pour carnet), adresse de carnet lue dans l'Anneau. Rien ne change tant que la stack n'a pas
les nouvelles variables : chaque ancien nom reste lu."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config, garde, main, maison

from .conftest import JETON, MDP, brancher_liseuse

COMMUN = "jeton-commun-essai"
ADRESSES_A_JETON = ("/generer", "/papier/imprime", "/synchroniser")


@pytest.fixture(autouse=True)
def _propre(monkeypatch):
    for v in ("MAISON_PASSWORD", "MAISON_JETON", "MAISON_JETON_ANCIEN", "MAISON_LECTURE_SEULE",
              "KIT_LECTURE_SEULE", "KIT_CARNET_URL"):
        monkeypatch.delenv(v, raising=False)


@pytest.fixture()
def client(jeu, monkeypatch):
    main.ETAT.clear()
    fausse = brancher_liseuse(monkeypatch)
    with TestClient(main.app) as c:
        c.liseuse = fausse
        yield c
    main.ETAT.clear()


@pytest.fixture()
def ecran(client):
    assert client.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200
    return client


def test_copie_du_module_non_retouchee():
    assert maison.CONTRAT == 1
    assert maison.empreinte_calculee() == maison.empreinte_ecrite()


# ---------------------------------------------------------------- mot de passe commun

def test_mot_de_passe_commun_puis_repli(monkeypatch, jeu):
    assert config.mot_de_passe() == MDP                                   # l'ancien KIT_PASSWORD seul
    monkeypatch.setenv("MAISON_PASSWORD", "mot-de-passe-commun")
    assert config.mot_de_passe() == "mot-de-passe-commun"                 # le commun l'emporte
    main.ETAT.clear()
    monkeypatch.setenv("KIT_PASSWORD", "")
    assert main.sessions().verifier_mot_de_passe("mot-de-passe-commun")   # suffit seul pour démarrer
    main.ETAT.clear()
    monkeypatch.delenv("MAISON_PASSWORD")
    with pytest.raises(SystemExit, match="MAISON_PASSWORD"):              # ni l'un ni l'autre : pas de démarrage
        main.sessions()
    main.ETAT.clear()


# ---------------------------------------------------------------- lecture seule

def test_lecture_seule_de_la_maison_et_forcage(ecran, monkeypatch):
    assert not garde.lecture_seule() and garde.origine() == ""
    monkeypatch.setenv("MAISON_LECTURE_SEULE", "oui")
    assert garde.lecture_seule()
    s = ecran.get("/api/session").json()
    assert s["lecture_seule"] is True and s["lecture_seule_origine"] == "maison"
    assert ecran.post("/api/livrer").status_code == 409
    assert ecran.get("/api/reglages").json()["lecture_seule_origine"] == "maison"
    monkeypatch.setenv("KIT_LECTURE_SEULE", "non")                       # le kit écrit malgré la maison
    assert not garde.lecture_seule() and garde.origine() == ""
    monkeypatch.delenv("MAISON_LECTURE_SEULE")
    monkeypatch.setenv("KIT_LECTURE_SEULE", "1")                         # « 1 » reste accepté, comme avant
    assert garde.lecture_seule() and garde.origine() == "appli"
    assert ecran.get("/api/session").json()["lecture_seule_origine"] == "appli"


# ---------------------------------------------------------------- jetons

def test_adresses_a_jeton_ouvertes_par_api_token_et_par_le_jeton_commun(client, monkeypatch):
    monkeypatch.setenv("MAISON_JETON", COMMUN)
    monkeypatch.setenv("KIT_LECTURE_SEULE", "1")       # /synchroniser répond 409 en lecture seule : jeton accepté
    for chemin in ADRESSES_A_JETON:
        for j in (JETON, COMMUN):
            r = client.post(chemin, headers={"Authorization": f"Bearer {j}"})
            assert r.status_code not in (401, 503), (chemin, j)
        assert client.post(chemin, headers={"Authorization": "Bearer faux"}).status_code == 401, chemin
        assert client.post(chemin).status_code == 401, chemin
    assert client.get("/cle-publique", headers={"Authorization": f"Bearer {COMMUN}"}).status_code == 200
    monkeypatch.setenv("MAISON_JETON_ANCIEN", "jeton-precedent")          # pendant un changement de jeton
    assert client.post("/generer", headers={"Authorization": "Bearer jeton-precedent"}).status_code == 200


def test_sans_jeton_commun_seul_api_token_ouvre(client):
    assert client.post("/generer", headers={"Authorization": f"Bearer {JETON}"}).status_code == 200
    assert client.post("/generer", headers={"Authorization": f"Bearer {COMMUN}"}).status_code == 401


def test_api_token_reste_obligatoire_meme_avec_le_jeton_commun(client, monkeypatch):
    """Home Assistant se sert d'API_TOKEN : sans lui, les adresses restent fermées, même avec MAISON_JETON."""
    monkeypatch.setenv("MAISON_JETON", COMMUN)
    monkeypatch.setenv("API_TOKEN", "")
    for chemin in ADRESSES_A_JETON:
        assert client.post(chemin, headers={"Authorization": f"Bearer {COMMUN}"}).status_code == 503, chemin


def test_le_jeton_commun_ne_donne_pas_l_interface(client, monkeypatch):
    monkeypatch.setenv("MAISON_JETON", COMMUN)
    assert client.get("/api/etat", headers={"Authorization": f"Bearer {COMMUN}"}).status_code == 401


# ---------------------------------------------------------------- adresse de carnet (annuaire de l'Anneau)

def test_adresse_de_carnet_par_l_annuaire_puis_repli(ecran, monkeypatch):
    services = [{"nom": "carnet", "locale": "http://nas.exemple:8096/", "privee": "https://nas.exemple.ts.net:8096"}]
    monkeypatch.setenv("KIT_CARNET_URL", "http://repli.exemple:8096")
    monkeypatch.setattr(config, "ANNUAIRE", maison.Annuaire(url="http://anneau.exemple", jeton=COMMUN,
                                                            lire=lambda: services))
    c = ecran.get("/api/livres").json()
    assert c["carnet"] == "http://nas.exemple:8096"
    assert c["contacts"][0]["carnet"] == "http://nas.exemple:8096/#/contacts/uid-voisine"
    assert ecran.get("/api/connexions").json()["carnet"]["url"] == "http://nas.exemple:8096"
    # page ouverte par Tailscale : l'adresse privée
    prive = ecran.get("/api/livres", headers={"Host": "nas.exemple.ts.net:8095"}).json()
    assert prive["carnet"] == "https://nas.exemple.ts.net:8096"

    def injoignable():
        raise OSError("pas d'Anneau")
    monkeypatch.setattr(config, "ANNUAIRE", maison.Annuaire(url="http://anneau.exemple", jeton=COMMUN, lire=injoignable))
    assert ecran.get("/api/livres").json()["carnet"] == "http://repli.exemple:8096"     # repli : KIT_CARNET_URL
    monkeypatch.setattr(config, "ANNUAIRE", maison.Annuaire(url="http://anneau.exemple", jeton="", lire=injoignable))
    assert ecran.get("/api/livres").json()["carnet"] == "http://repli.exemple:8096"     # sans jeton commun : repli
