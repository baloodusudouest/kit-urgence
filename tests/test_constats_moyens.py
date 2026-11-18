"""Constats moyens de l'audit du 17/11/2026 corrigés en 2.5.7 : délais des outils (M43),
mot de passe des papiers trop court et empreinte lente salée (M45)."""
from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app import config, controle, generate, main, status

from .conftest import MDP, MDP_PAPIERS, brancher_liseuse


# ---------------------------------------------------------------- M43 : délais de pandoc et qpdf

def test_un_pandoc_qui_ne_finit_pas_est_arrete_et_dit(jeu, monkeypatch):
    monkeypatch.setattr(generate, "DELAI_PANDOC", 0.001)
    etat = generate.generer(config.load())
    raisons = [e["raison"] for e in etat["controle"]["echecs"]]
    assert raisons and all("plus de" in r and "sans finir" in r for r in raisons)


def test_un_qpdf_qui_ne_repond_pas_fait_echouer_le_controle(jeu, monkeypatch):
    generate.generer(config.load())
    livre = generate.SORTIE / generate.NOM_05
    monkeypatch.setattr(controle, "DELAI_QPDF", 0.001)
    with pytest.raises(controle.Echec, match="ne s'est pas rouvert"):
        controle.papiers(livre, MDP_PAPIERS, 1)


# ---------------------------------------------------------------- M45 : mot de passe trop court

def test_un_mot_de_passe_des_papiers_trop_court_est_refuse_sans_arreter_le_reste(jeu, monkeypatch):
    monkeypatch.setenv("PAPIERS_PASSWORD", "court-11car")          # 11 caractères
    etat = generate.generer(config.load())
    assert generate.NOM_05 not in etat["livres"]
    assert generate.NOM_00 in etat["livres"] and generate.NOM_02 in etat["livres"]
    assert any("trop court" in a and "12 caractères" in a for a in etat["avertissements"])


def test_l_ecran_dit_que_le_mot_de_passe_des_papiers_est_trop_court(jeu, monkeypatch):
    monkeypatch.setenv("PAPIERS_PASSWORD", "court-11car")
    main.ETAT.clear()
    brancher_liseuse(monkeypatch)
    with TestClient(main.app) as c:                                 # l'appli démarre quand même
        assert c.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200
        reglages = c.get("/api/reglages").json()
        assert "trop court" in reglages["mot_de_passe_papiers_probleme"]
        livres = c.get("/api/livres").json()
        papiers = next(l for l in (livres["livres"] if isinstance(livres, dict) else livres)
                       if l["fichier"] == generate.NOM_05)
        assert "trop court" in papiers["attente"]
    main.ETAT.clear()


# ---------------------------------------------------------------- M45 : empreinte lente et salée

def _sur_disque() -> str:
    return (config.STATE / "livres.json").read_text(encoding="utf-8") + (config.STATE / "status.json").read_text(
        encoding="utf-8")


def test_l_empreinte_du_mot_de_passe_est_lente_et_salee(jeu):
    e = config.empreinte_papiers(MDP_PAPIERS)
    sel = config.SEL_PAPIERS.read_text(encoding="utf-8")
    attendu = hashlib.pbkdf2_hmac("sha256", MDP_PAPIERS.encode(), bytes.fromhex(sel), config.TOURS_PAPIERS).hex()
    assert e == "pbkdf2:" + attendu
    assert (config.SEL_PAPIERS.stat().st_mode & 0o777) == 0o600


def test_aucune_empreinte_rapide_du_mot_de_passe_n_est_gardee(jeu):
    cfg = config.load()
    generate.generer(cfg)
    rapide = hashlib.sha256(MDP_PAPIERS.encode()).hexdigest()
    docs = generate.papiers.sources(config.DATA / "papiers")
    reg = json.loads((config.STATE / "livres.json").read_text(encoding="utf-8"))
    assert reg[generate.NOM_05]["entree"] != generate.sha_entrees(rapide, *docs)
    assert status.read()["sources"] != generate.sha_sources(cfg, ancienne=True)
    assert rapide not in _sur_disque()


def test_les_anciennes_empreintes_sont_relues_puis_reecrites(jeu):
    cfg = config.load()
    generate.generer(cfg)
    reg = json.loads((config.STATE / "livres.json").read_text(encoding="utf-8"))
    date_05, sha_05 = reg[generate.NOM_05]["date"], reg[generate.NOM_05]["sha"]
    docs = generate.papiers.sources(config.DATA / "papiers")
    # État laissé par la 2.5.6 : empreintes rapides
    reg[generate.NOM_05]["entree"] = generate.entree_papiers(cfg, docs, ancienne=True)
    (config.STATE / "livres.json").write_text(json.dumps(reg), encoding="utf-8")
    status.update(sources=generate.sha_sources(cfg, ancienne=True),
                  essai={"le": status.now(), "mot_de_passe": config.empreinte_essai_ancienne(MDP_PAPIERS)})

    assert generate.reprendre_empreintes_anciennes(cfg) == 3
    assert generate.reprendre_empreintes_anciennes(cfg) == 0           # une seule fois
    etat = status.read()
    assert etat["sources"] == generate.sha_sources(cfg)
    assert etat["essai"]["mot_de_passe"] == config.empreinte_papiers(MDP_PAPIERS)
    # Le livre des papiers n'est pas refait (même date), et l'essai n'est pas redemandé
    nouveau = generate.generer(cfg)
    reg = json.loads((config.STATE / "livres.json").read_text(encoding="utf-8"))
    assert reg[generate.NOM_05]["date"] == date_05 and generate.NOM_05 in nouveau["livres"]
    assert reg[generate.NOM_05]["sha"] == sha_05                      # le chiffrement change à chaque fabrication
    from app import etat as ecran
    assert ecran.essai(cfg, status.read())["mot_de_passe_change"] is False

