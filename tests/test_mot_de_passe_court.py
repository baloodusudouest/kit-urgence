"""2.6.1 (choix de Julien) : un mot de passe des papiers court (< 12 caractères) ne donne plus qu'un
avertissement ; le livre des papiers est fabriqué et chiffré comme avant, rien n'est proposé au retrait."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import config, controle, generate, main, status

from .conftest import MDP, brancher_liseuse

COURT = "court-11car"                                                 # 11 caractères, inventé
AVERTISSEMENT = "mot de passe des papiers court (11 caractères) : 12 au moins conseillés"


def _registre() -> dict:
    return json.loads((config.STATE / "livres.json").read_text(encoding="utf-8"))


def test_un_mot_de_passe_court_fabrique_le_livre_chiffre_avec_un_avertissement(jeu, monkeypatch):
    monkeypatch.setenv("PAPIERS_PASSWORD", COURT)
    etat = generate.generer(config.load())
    assert generate.NOM_05 in etat["livres"] and not etat["disparitions"]
    assert etat["controle"]["ok"] is True
    controle.papiers(generate.SORTIE / generate.NOM_05, COURT, 1)    # chiffré, rouvert avec ce mot de passe
    assert any(AVERTISSEMENT in a for a in etat["avertissements"])
    assert not any("non généré" in a for a in etat["avertissements"])


def test_l_ecran_avertit_sans_bloquer(jeu, monkeypatch):
    monkeypatch.setenv("PAPIERS_PASSWORD", COURT)
    main.ETAT.clear()
    brancher_liseuse(monkeypatch)
    with TestClient(main.app) as c:
        assert c.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200
        reglages = c.get("/api/reglages").json()
        assert reglages["mot_de_passe_papiers_probleme"] == ""
        assert reglages["mot_de_passe_papiers_avertissement"] == AVERTISSEMENT
        livres = c.get("/api/livres").json()
        papiers = next(l for l in (livres["livres"] if isinstance(livres, dict) else livres)
                       if l["fichier"] == generate.NOM_05)
        assert papiers["avertissement"] == AVERTISSEMENT
    main.ETAT.clear()


def test_un_mot_de_passe_assez_long_ne_donne_aucun_avertissement(jeu):
    cfg = config.load()
    assert cfg.papiers_avertissement == ""
    etat = generate.generer(cfg)
    assert not any("court" in a for a in etat["avertissements"])


def test_un_mot_de_passe_absent_reste_comme_avant(jeu, monkeypatch):
    monkeypatch.setenv("PAPIERS_PASSWORD", "")
    cfg = config.load()
    assert cfg.papiers_avertissement == ""
    etat = generate.generer(cfg)
    assert generate.NOM_05 not in etat["livres"]
    assert any("05 – Papiers non généré" in a and "absent" in a for a in etat["avertissements"])


def test_depuis_la_2_5_6_un_livre_fait_avec_un_mot_de_passe_court_n_est_ni_refait_ni_retire(jeu, monkeypatch):
    monkeypatch.setenv("PAPIERS_PASSWORD", COURT)
    cfg = config.load()
    generate.generer(cfg)
    reg = _registre()
    date_05, sha_05 = reg[generate.NOM_05]["date"], reg[generate.NOM_05]["sha"]
    docs = generate.papiers.sources(config.DATA / "papiers")
    # État laissé par la 2.5.6 : empreinte SHA-256 ancienne dans le registre et dans l'état
    reg[generate.NOM_05]["entree"] = generate.entree_papiers(cfg, docs, ancienne=True)
    (config.STATE / "livres.json").write_text(json.dumps(reg), encoding="utf-8")
    status.update(sources=generate.sha_sources(cfg, ancienne=True))

    assert generate.reprendre_empreintes_anciennes(cfg) == 2          # registre + sources
    etat = generate.generer(cfg)
    reg = _registre()
    assert reg[generate.NOM_05]["date"] == date_05 and reg[generate.NOM_05]["sha"] == sha_05   # pas refait
    assert generate.NOM_05 in etat["livres"]
    assert etat["disparitions"] == []                                  # pas proposé au retrait
    assert status.read()["sources"] == generate.sha_sources(cfg)
