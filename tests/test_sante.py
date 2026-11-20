"""2.6.0 : santé des tâches de fond dans /health (socle 0.9.0).

Tâches suivies : « scrutation » (régulière, toutes les scrutation_secondes), « fabrication » et « livraison »
(à la demande). Pas de base SQLite : copie_base vaut null."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app import __version__, config, generate, main, maison, sync

from .conftest import JETON, MDP, brancher_liseuse

COMMUN = "jeton-commun-essai"
PORTEUR = {"Authorization": f"Bearer {JETON}"}


@pytest.fixture()
def client(jeu, monkeypatch):
    for v in ("MAISON_JETON", "MAISON_JETON_ANCIEN", "MAISON_LECTURE_SEULE", "KIT_LECTURE_SEULE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("MAISON_PASSWORD", MDP)
    main.ETAT.clear()
    fausse = brancher_liseuse(monkeypatch)
    with TestClient(main.app) as c:
        c.liseuse = fausse
        yield c
    main.ETAT.clear()


def _tache(corps: dict, nom: str) -> dict:
    return next(t for t in corps["taches"] if t["nom"] == nom)


def test_health_porte_la_sante_sans_message_sans_jeton(client, monkeypatch):
    monkeypatch.setenv("MAISON_JETON", COMMUN)
    corps = client.get("/health").json()
    assert corps["ok"] is True and corps["version"] == __version__          # rien d'existant ne change
    assert corps["version_socle"] == maison.VERSION_SOCLE == "0.11.0"
    assert corps["copie_base"] is None                                      # pas de base SQLite
    noms = {t["nom"]: t for t in corps["taches"]}
    assert noms["fabrication"]["type"] == "demande" and noms["livraison"]["type"] == "demande"
    assert all("message" not in t for t in corps["taches"])
    # API_TOKEN (Home Assistant) n'ouvre pas les messages ; le jeton commun et la session, oui
    assert all("message" not in t for t in client.get("/health", headers=PORTEUR).json()["taches"])
    avec = client.get("/health", headers={"Authorization": f"Bearer {COMMUN}"}).json()
    assert all("message" in t for t in avec["taches"])
    assert client.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200
    assert all("message" in t for t in client.get("/health").json()["taches"])


def test_fabrication_et_livraison_suivies(client):
    assert client.post("/generer", headers=PORTEUR).json()["derniere_erreur"] is None
    assert client.post("/synchroniser", headers=PORTEUR).json()["a_jour"] is True
    corps = client.get("/health").json()
    assert _tache(corps, "fabrication")["etat"] == "ok"
    assert _tache(corps, "livraison")["etat"] == "ok"


def test_fabrication_ratee_passe_en_erreur(client, monkeypatch):
    monkeypatch.setenv("MAISON_JETON", COMMUN)

    def casse(cfg, forcer=False):
        raise RuntimeError("pandoc introuvable")

    monkeypatch.setattr(generate, "generer", casse)
    e = client.post("/generer", headers=PORTEUR).json()
    assert "pandoc introuvable" in e["derniere_erreur"]                     # comportement d'avant inchangé
    t = _tache(client.get("/health", headers={"Authorization": f"Bearer {COMMUN}"}).json(), "fabrication")
    assert t["etat"] == "erreur" and t["message"] == "RuntimeError: pandoc introuvable"


def test_scrutation_ratee_passe_en_retard(jeu, monkeypatch):
    """Un tour qui échoue est avalé comme avant (la boucle continue) mais la tâche passe en retard."""
    base = time.time()
    horloge = {"t": base}
    monkeypatch.setattr(maison.TACHES, "horloge", lambda: horloge["t"])
    brancher_liseuse(monkeypatch)
    cfg = config.load()
    memoire = {"deja_livre": True, "dernier_vu": time.monotonic()}

    main._tour_de_scrutation(cfg, memoire)                                  # un tour qui marche
    assert _etat("scrutation") == "ok"

    def panne(cfg, delai=2.0):
        raise OSError("réseau coupé")

    monkeypatch.setattr(sync, "port_ouvert", panne)
    horloge["t"] = base + 30
    main._tour_de_scrutation(cfg, memoire)                                  # n'élève rien
    horloge["t"] = base + 2 * 60 + 601                                      # 2 × période + 10 min
    assert _etat("scrutation") == "en_retard"


def _etat(nom: str) -> str:
    return next(t for t in maison.TACHES.etat() if t["nom"] == nom)["etat"]
