"""Variables communes de la maison (module app/maison.py du socle, copié tel quel) et, depuis la 2.5.0,
réglages sauvegardés chez l'Anneau.

2.4.0 : mot de passe commun, lecture seule de toute la maison, jeton commun accepté en plus d'API_TOKEN sur les
adresses à jeton (pour carnet), adresse de carnet lue dans l'Anneau.
2.5.0 : les anciens noms ne sont plus lus (KIT_PASSWORD, KIT_CARNET_URL) ; KIT_LECTURE_SEULE reste (forçage
pour le kit seul) ; API_TOKEN reste obligatoire (Home Assistant). Sauvegarde et restauration des réglages."""
from __future__ import annotations

import urllib.error

import pytest
from fastapi.testclient import TestClient

from app import __version__, config, garde, main, maison, sauvegarde

from .conftest import JETON, MDP, MDP_PAPIERS, brancher_liseuse

COMMUN = "jeton-commun-essai"
ADRESSES_A_JETON = ("/generer", "/papier/imprime", "/synchroniser")


@pytest.fixture(autouse=True)
def _propre(monkeypatch):
    for v in ("MAISON_JETON", "MAISON_JETON_ANCIEN", "MAISON_LECTURE_SEULE", "KIT_LECTURE_SEULE",
              "KIT_CARNET_URL", "KIT_PASSWORD", "MAISON_ANNEAU_URL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("MAISON_PASSWORD", MDP)
    monkeypatch.setattr(main, "LIRE_ANNEAU", None)


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
    assert maison.CONTRAT == 3 and maison.CONTRAT_SAUVEGARDE == 1
    assert maison.empreinte_calculee() == maison.empreinte_ecrite()


# ---------------------------------------------------------------- mot de passe commun

def test_mot_de_passe_commun_seul(monkeypatch, jeu):
    assert config.mot_de_passe() == MDP
    main.ETAT.clear()
    assert main.sessions().verifier_mot_de_passe(MDP)
    main.ETAT.clear()
    monkeypatch.delenv("MAISON_PASSWORD")
    monkeypatch.setenv("KIT_PASSWORD", "ancien-mot-de-passe-du-kit")      # l'ancien nom seul ne suffit plus
    assert config.mot_de_passe() == ""
    with pytest.raises(SystemExit, match="MAISON_PASSWORD est absent ou trop court"):
        main.sessions()
    main.ETAT.clear()
    monkeypatch.setenv("MAISON_PASSWORD", "court")                       # moins de 12 caractères : refus
    with pytest.raises(SystemExit, match="MAISON_PASSWORD est absent ou trop court"):
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


# ---------------------------------------------------------------- jetons (portes reçues)

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


# ---------------------------------------------------------------- adresse de carnet (annuaire de l'Anneau seul)

def test_adresse_de_carnet_par_l_annuaire_seul(ecran, monkeypatch):
    services = [{"nom": "carnet", "locale": "http://nas.exemple:8096/", "privee": "https://nas.exemple.ts.net:8096"}]
    monkeypatch.setenv("KIT_CARNET_URL", "http://repli.exemple:8096")     # ancien nom : plus jamais lu
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
    assert ecran.get("/api/livres").json()["carnet"] in (None, "")          # pas de repli : pas de lien
    assert "repli.exemple" not in str(ecran.get("/api/livres").json())


# ---------------------------------------------------------------- sauvegarde des réglages (2.5, contrat 1)

def test_sauvegarde_porte_fermee_sans_jeton_commun(client, monkeypatch):
    assert client.get("/externe/sauvegarde").status_code == 404                        # MAISON_JETON vide
    assert client.get("/externe/sauvegarde", headers={"Authorization": f"Bearer {JETON}"}).status_code == 404
    monkeypatch.setenv("MAISON_JETON", COMMUN)
    assert client.get("/externe/sauvegarde").status_code == 401
    assert client.get("/externe/sauvegarde", headers={"Authorization": "Bearer faux"}).status_code == 401
    # API_TOKEN (Home Assistant) n'ouvre pas cette porte : jeton commun seul
    assert client.get("/externe/sauvegarde", headers={"Authorization": f"Bearer {JETON}"}).status_code == 401


def test_sauvegarde_rend_les_reglages_sans_secret(client, monkeypatch):
    monkeypatch.setenv("MAISON_JETON", COMMUN)
    r = client.get("/externe/sauvegarde", headers={"Authorization": f"Bearer {COMMUN}"})
    assert r.status_code == 200
    d = r.json()
    assert d["contrat"] == 1 and d["appli"] == "kit-urgence" and d["version"] == __version__
    assert d["reglages"] == {"titre_foyer": "Maison des Tilleuls", "liseuse_adresse": "127.0.0.1", "liseuse_port": 2222,
                             "liseuse_dossier": d["reglages"]["liseuse_dossier"], "scrutation_secondes": 60}
    texte = r.text
    for cle in sauvegarde.EXCLUS:
        assert cle not in d["reglages"]
    for interdit in (MDP, MDP_PAPIERS, JETON, COMMUN, "ssh-ed25519", "root", "contacts-urgence", "PAPIERS_PASSWORD",
                     "MAISON_", "API_TOKEN", "01-carte"):
        assert interdit not in texte, interdit


class FauxAnneau:
    """Répond comme l'Anneau à GET /externe/sauvegardes/kit-urgence[?le=…]."""

    def __init__(self, sauvegardes: dict):
        self.sauvegardes = sauvegardes
        self.demandes: list[tuple[str, str]] = []

    def __call__(self, adresse: str, jeton: str) -> dict:
        self.demandes.append((adresse, jeton))
        assert "/externe/sauvegardes/kit-urgence" in adresse
        if "?le=" not in adresse:
            return {"dates": sorted(self.sauvegardes, reverse=True)}
        le = adresse.split("?le=")[1]
        if le not in self.sauvegardes:
            raise urllib.error.HTTPError(adresse, 404, "Not Found", {}, None)
        return {"le": le, "version": "2.5.0", "reglages": self.sauvegardes[le]}


def test_restaurer_dates_differences_application(ecran, monkeypatch):
    monkeypatch.setenv("MAISON_JETON", COMMUN)
    anneau = FauxAnneau({
        "2026-11-14": {"titre_foyer": "Maison des Tilleuls"},
        "2026-11-15": {"titre_foyer": "Maison du Verger", "scrutation_secondes": 300, "liseuse_port": 2222,
                       "liseuse_utilisateur": "pirate",               # clé exclue : jamais appliquée
                       "mot_de_passe_papiers": "x", "inconnu": 1},    # secret et clé inconnue : ignorés
    })
    monkeypatch.setattr(main, "LIRE_ANNEAU", anneau)
    assert ecran.get("/api/restaurer").json() == {"dates": ["2026-11-15", "2026-11-14"]}
    assert anneau.demandes[-1][1] == COMMUN                             # le jeton commun part vers l'Anneau
    v = ecran.get("/api/restaurer", params={"le": "2026-11-15"}).json()
    assert v["le"] == "2026-11-15" and v["version"] == "2.5.0"
    assert v["differences"] == [
        {"cle": "scrutation_secondes", "actuel": 60, "sauve": 300},
        {"cle": "titre_foyer", "actuel": "Maison des Tilleuls", "sauve": "Maison du Verger"},
    ]
    r = ecran.post("/api/restaurer", json={"le": "2026-11-15"})
    assert r.status_code == 200
    d = r.json()
    assert d["titre_foyer"] == "Maison du Verger" and d["scrutation_secondes"] == 300
    assert d["liseuse"]["user"] == "root"                              # l'utilisateur SSH n'a pas bougé
    assert sorted(d["appliques"]) == ["scrutation_secondes", "titre_foyer"]
    assert any("restaurés" in l["quoi"] and "2026-11-15" in l["quoi"] for l in d["journal"])
    assert config.load().titre_foyer == "Maison du Verger"
    assert ecran.get("/api/restaurer", params={"le": "2026-11-15"}).json()["differences"] == []
    assert ecran.get("/api/restaurer", params={"le": "2026-11-01"}).status_code == 404       # rien ce jour-là
    assert ecran.get("/api/restaurer", params={"le": "hier"}).status_code == 400
    assert ecran.post("/api/restaurer", json={}).status_code == 400


def test_restaurer_refuse_en_lecture_seule_et_valeur_refusee(ecran, monkeypatch):
    monkeypatch.setenv("MAISON_JETON", COMMUN)
    monkeypatch.setattr(main, "LIRE_ANNEAU", FauxAnneau({"2026-11-15": {"titre_foyer": "Maison du Verger"},
                                                         "2026-11-16": {"liseuse_dossier": "/"}}))
    monkeypatch.setenv("MAISON_LECTURE_SEULE", "oui")                        # 2.5.1 : refusé en lecture seule
    assert ecran.post("/api/restaurer", json={"le": "2026-11-15"}).status_code == 409
    assert config.load().titre_foyer != "Maison du Verger"
    monkeypatch.setenv("MAISON_LECTURE_SEULE", "")
    assert ecran.post("/api/restaurer", json={"le": "2026-11-15"}).status_code == 200
    assert config.load().titre_foyer == "Maison du Verger"
    r = ecran.post("/api/restaurer", json={"le": "2026-11-16"})              # dossier dangereux : mêmes contrôles
    assert r.status_code == 422 and "non appliquée" in r.json()["detail"]
    assert config.load().kindle.dossier != "/"


def test_restaurer_anneau_injoignable_ou_sans_jeton(ecran, monkeypatch):
    r = ecran.get("/api/restaurer")                                     # pas de jeton commun : message clair
    assert r.status_code == 503 and "MAISON_JETON" in r.json()["detail"]
    assert ecran.get("/api/reglages").json()["sauvegarde_possible"] is False
    monkeypatch.setenv("MAISON_JETON", COMMUN)
    assert ecran.get("/api/reglages").json()["sauvegarde_possible"] is True

    def injoignable(adresse, jeton):
        raise urllib.error.URLError("pas d'Anneau")
    monkeypatch.setattr(main, "LIRE_ANNEAU", injoignable)
    for r in (ecran.get("/api/restaurer"), ecran.get("/api/restaurer", params={"le": "2026-11-15"}),
              ecran.post("/api/restaurer", json={"le": "2026-11-15"})):
        assert r.status_code == 503 and "Anneau ne répond pas" in r.json()["detail"]
    ecran.cookies.clear()
    assert ecran.get("/api/restaurer").status_code == 401                 # session obligatoire
    assert ecran.post("/api/restaurer", json={"le": "2026-11-15"}).status_code == 401
