"""API du générateur kit-urgence + scrutation du Kindle.

- GET  /status              état lu par Home Assistant (capteurs REST)
- POST /generer             reconstruit le kit (bouton HA)
- POST /synchroniser        livre tout de suite si le Kindle répond
- POST /papier/imprime      confirme que la version papier a été imprimée
- GET  /cle-publique        clé à ajouter dans koreader/settings/SSH/authorized_keys
"""
from __future__ import annotations

import logging
import os
import threading
import time

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse

from . import config, generate, status, sync

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kit")
for bavard in ("weasyprint", "fontTools"):
    logging.getLogger(bavard).setLevel(logging.ERROR)

API_TOKEN = os.environ.get("API_TOKEN", "")
_TRAVAIL = threading.Lock()  # une seule génération / livraison à la fois

app = FastAPI(title="kit-urgence", version="1.0.1")


def _auth(authorization: str = Header(default="")) -> None:
    if API_TOKEN and authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Jeton invalide")


def _generer_si_besoin(cfg: config.Config, forcer: bool = False) -> None:
    etat = status.read()
    if forcer or not etat.get("version_nas") or etat.get("sources") != generate.sha_sources(cfg):
        log.info("Génération du kit…")
        generate.generer(cfg)


def _session_kindle(cfg: config.Config) -> dict:
    """Régénère si les sources ont changé, puis livre et vérifie."""
    with _TRAVAIL:
        try:
            _generer_si_besoin(cfg)
            return sync.livrer(cfg)
        except Exception as exc:  # noqa: BLE001 — l'erreur est remontée à HA
            log.exception("Échec de la livraison")
            return status.update(derniere_erreur=f"{status.now()} : {exc}")


def _scrutation() -> None:
    """Détecte l'apparition du Kindle (port SSH ouvert) et livre une fois par présence."""
    deja_livre = False
    while True:
        cfg = config.load()
        try:
            joignable = sync.port_ouvert(cfg)
            if joignable != status.read().get("kindle_joignable"):
                status.update(kindle_joignable=joignable)
                log.info("Kindle %s", "joignable" if joignable else "hors ligne")
            if joignable and not deja_livre:
                etat = _session_kindle(cfg)
                deja_livre = etat.get("derniere_erreur") is None
            if not joignable:
                deja_livre = False
        except Exception:  # noqa: BLE001
            log.exception("Erreur de scrutation")
        time.sleep(max(15, cfg.scrutation_secondes))


@app.on_event("startup")
def _demarrage() -> None:
    cle = sync.assurer_cle()
    log.info("Clé publique à autoriser sur le Kindle :\n%s", cle)
    cfg = config.load()
    with _TRAVAIL:
        try:
            _generer_si_besoin(cfg)
        except Exception as exc:  # noqa: BLE001
            log.exception("Génération initiale impossible")
            status.update(derniere_erreur=f"{status.now()} : {exc}")
    threading.Thread(target=_scrutation, daemon=True, name="scrutation").start()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/status")
def get_status() -> dict:
    etat = status.read()
    etat.pop("sources", None)
    return etat


@app.get("/cle-publique", response_class=PlainTextResponse)
def cle_publique() -> str:
    return sync.assurer_cle() + "\n"


@app.post("/generer", dependencies=[Depends(_auth)])
def generer() -> dict:
    cfg = config.load()
    with _TRAVAIL:
        try:
            return generate.generer(cfg, forcer=True)
        except Exception as exc:  # noqa: BLE001
            log.exception("Échec de la génération")
            return status.update(derniere_erreur=f"{status.now()} : {exc}")


@app.post("/synchroniser", dependencies=[Depends(_auth)])
def synchroniser() -> dict:
    cfg = config.load()
    if not sync.port_ouvert(cfg):
        raise HTTPException(status_code=409, detail="Kindle injoignable : ouvre KOReader et démarre le SSH")
    return _session_kindle(cfg)


@app.post("/papier/imprime", dependencies=[Depends(_auth)])
def papier_imprime() -> dict:
    etat = status.read()
    return status.update(version_papier_imprimee=etat.get("version_papier"))
