"""Kit d'urgence : générateur, livraison vers la liseuse, et (2.0.0) interface.

Deux portes, deux clés :
- l'interface et `/api/…` : mot de passe commun (KIT_PASSWORD), session par cookie ;
- `/generer`, `/synchroniser`, `/papier/imprime` : jeton de Home Assistant et de carnet (API_TOKEN).
  Un jeton vide ne vaut plus « ouvert à tous » : ces adresses refusent tant qu'il n'est pas réglé.
Sans clé : `/health` et `/status` (lu par les capteurs de Home Assistant ; aucun nom de papier dedans).
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from . import __version__, config, ecrits, etat, generate, journal, status, sync
from .auth import COMMUN, DUREE, Sessions
from .garde import LectureSeule, exiger_ecriture, lecture_seule

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kit")
for bavard in ("weasyprint", "fontTools"):
    logging.getLogger(bavard).setLevel(logging.ERROR)

_TRAVAIL = threading.Lock()  # une seule génération / livraison à la fois
STATIQUE = Path(__file__).parent / "static"
GENERATION = config.STATE / "session_generation"
ETAT: dict = {}

app = FastAPI(title="kit-urgence", version=__version__, docs_url=None, redoc_url=None)


def jeton() -> str:
    return os.environ.get("API_TOKEN", "")


def sessions() -> Sessions:
    if "sessions" not in ETAT:
        mdp = config.mot_de_passe()
        if not mdp:
            raise SystemExit("KIT_PASSWORD est absent : le kit d'urgence ne démarre pas sans mot de passe.")
        try:
            generation = int(GENERATION.read_text().strip())
        except (OSError, ValueError):
            generation = 0
        ETAT["sessions"] = Sessions("kit", mdp, generation)
    return ETAT["sessions"]


# ================================================================ sécurité

@app.middleware("http")
async def garde(request: Request, appel):
    chemin = request.url.path
    if chemin.startswith("/api/"):
        libre = chemin == "/api/session" or (chemin == "/api/connexion" and request.method == "POST")
        s = sessions()
        if not libre and not s.connecte(request.cookies):
            return JSONResponse({"detail": "Connexion nécessaire."}, status_code=401)
    reponse = await appel(request)
    if chemin.startswith("/api/"):
        reponse.headers["Cache-Control"] = "no-store"
    return reponse


@app.exception_handler(ecrits.Refus)
async def _refus(_: Request, exc: ecrits.Refus):
    return JSONResponse({"detail": str(exc)}, status_code=exc.code)


@app.exception_handler(LectureSeule)
async def _lecture_seule(_: Request, exc: LectureSeule):
    return JSONResponse({"detail": str(exc)}, status_code=409)


def _auth(authorization: str = Header(default="")) -> None:
    """Jeton de Home Assistant et de carnet. Vide = refusé (avant la 2.0.0 : ouvert à tous)."""
    attendu = jeton()
    if not attendu:
        raise HTTPException(503, "Jeton non réglé : définis KIT_API_TOKEN dans la stack.")
    if authorization != f"Bearer {attendu}":
        raise HTTPException(401, "Jeton invalide")
    status.update(dernier_appel_jeton=status.now())


# ================================================================ travail

def _generer_si_besoin(cfg: config.Config, forcer: bool = False) -> None:
    e = status.read()
    if forcer or not e.get("version_nas") or e.get("sources") != generate.sha_sources(cfg):
        log.info("Génération du kit…")
        generate.generer(cfg)


def _generer(cfg: config.Config, forcer: bool = True) -> dict:
    with _TRAVAIL:
        try:
            return generate.generer(cfg, forcer=forcer)
        except Exception as exc:  # noqa: BLE001 — l'erreur est montrée à l'écran et à Home Assistant
            log.exception("Échec de la génération")
            return status.update(derniere_erreur=f"{status.now()} : {exc}")


def _session_kindle(cfg: config.Config) -> dict:
    """Régénère si les sources ont changé, puis livre et vérifie."""
    with _TRAVAIL:
        try:
            _generer_si_besoin(cfg)
            return sync.livrer(cfg)
        except LectureSeule:
            raise
        except Exception as exc:  # noqa: BLE001 — l'erreur est remontée à HA
            log.exception("Échec de la livraison")
            return status.update(derniere_erreur=f"{status.now()} : {exc}")


def _scrutation() -> None:
    """Détecte l'apparition de la liseuse (port SSH ouvert) et livre une fois par présence."""
    deja_livre = False
    dernier_vu = 0.0
    while True:
        cfg = config.load()
        try:
            joignable = sync.port_ouvert(cfg)
            if joignable != status.read().get("kindle_joignable"):
                status.update(kindle_joignable=joignable)
                log.info("Liseuse %s", "joignable" if joignable else "hors ligne")
            if joignable and time.monotonic() - dernier_vu > 3600:     # « vue le » : une écriture par heure au plus
                status.update(kindle_vu_le=status.now())
                dernier_vu = time.monotonic()
            if joignable and not deja_livre and not lecture_seule():
                e = _session_kindle(cfg)
                deja_livre = e.get("derniere_erreur") is None
            if not joignable:
                deja_livre = False
        except Exception:  # noqa: BLE001
            log.exception("Erreur de scrutation")
        time.sleep(max(15, cfg.scrutation_secondes))


@app.on_event("startup")
def _demarrage() -> None:
    sessions()                                   # refuse de démarrer sans mot de passe
    if not jeton():
        log.warning("API_TOKEN est vide : Home Assistant et carnet ne pourront rien lancer.")
    cle = sync.assurer_cle()
    log.info("Clé publique à autoriser sur la liseuse :\n%s", cle)
    cfg = config.load()
    with _TRAVAIL:
        try:
            _generer_si_besoin(cfg)
        except Exception as exc:  # noqa: BLE001
            log.exception("Génération initiale impossible")
            status.update(derniere_erreur=f"{status.now()} : {exc}")
    if not os.environ.get("KIT_SANS_SCRUTATION"):
        threading.Thread(target=_scrutation, daemon=True, name="scrutation").start()


# ================================================================ sans clé

@app.get("/health")
def health() -> dict:
    return {"ok": True, "version": __version__}


@app.get("/status")
def get_status() -> dict:
    """Lu par Home Assistant. Mêmes clés qu'en 1.0 ; les réglages internes n'en sortent pas."""
    e = status.read()
    for interne in ("sources", "papier_instantane", "essai", "disparitions_acceptees", "dernier_appel_jeton"):
        e.pop(interne, None)
    e["a_traiter"] = etat.nombre_a_traiter(config.load())
    e["version"] = __version__
    return e


# ================================================================ par jeton (Home Assistant, carnet)

@app.get("/cle-publique", response_class=PlainTextResponse, dependencies=[Depends(_auth)])
def cle_publique() -> str:
    return sync.assurer_cle() + "\n"


@app.post("/generer", dependencies=[Depends(_auth)])
def generer() -> dict:
    journal.noter("Kit refabriqué", par="jeton")
    return _generer(config.load())


@app.post("/synchroniser", dependencies=[Depends(_auth)])
def synchroniser() -> dict:
    exiger_ecriture("sur la liseuse")
    cfg = config.load()
    if not sync.port_ouvert(cfg):
        raise HTTPException(status_code=409, detail="Kindle injoignable : ouvre KOReader et démarre le SSH")
    journal.noter("Kit livré sur la liseuse", par="jeton")
    return _session_kindle(cfg)


@app.post("/papier/imprime", dependencies=[Depends(_auth)])
def papier_imprime() -> dict:
    journal.noter("Version papier marquée imprimée", par="jeton")
    return _papier_imprime()


def _papier_imprime() -> dict:
    cfg = config.load()
    return status.update(version_papier_imprimee=status.read().get("version_papier"),
                         papier_instantane=generate.instantane_papier(cfg),
                         papier_imprime_le=status.now())


# ================================================================ connexion à l'interface

@app.get("/api/session")
def session(request: Request):
    s = sessions()
    return {"connecte": s.connecte(request.cookies), "version": __version__,
            "lecture_seule": lecture_seule()}


@app.post("/api/connexion")
async def connexion(corps: dict = Body(...)):
    s = sessions()
    if not os.environ.get("KIT_SANS_ATTENTE"):
        await asyncio.sleep(s.attente())
    if not s.verifier_mot_de_passe(str(corps.get("mot_de_passe", ""))):
        raise HTTPException(401, "Mot de passe incorrect.")
    r = JSONResponse({"ok": True})
    r.set_cookie(s.cookie, s.creer(), max_age=DUREE, httponly=True, samesite="strict")
    return r


@app.post("/api/deconnexion")
def deconnexion():
    s = sessions()
    s.generation += 1
    try:
        GENERATION.parent.mkdir(parents=True, exist_ok=True)
        GENERATION.write_text(str(s.generation))
    except OSError:
        pass
    r = JSONResponse({"ok": True})
    r.delete_cookie(s.cookie)
    r.delete_cookie(COMMUN)      # « Se déconnecter » ferme aussi la connexion commune
    return r


# ================================================================ lecture pour l'écran

@app.get("/api/etat")
def api_etat():
    return etat.tuiles(config.load())


@app.get("/api/livres")
def api_livres():
    cfg = config.load()
    return {"livres": etat.livres(cfg), "textes": etat.textes(), "guides": etat.guides(),
            "papiers": etat.liste_papiers(), "pieces": ecrits.pieces(), "retires": ecrits.papiers_retires(), "numeros": etat.numeros(),
            **etat.liste_contacts(cfg)}


@app.get("/api/textes/{nom}")
def api_texte(nom: str):
    chemin = _texte(nom)
    return {"nom": chemin.name, "contenu": chemin.read_text(encoding="utf-8"), "versions": ecrits.versions(chemin)}


@app.get("/api/textes/{nom}/versions/{ident}")
def api_version(nom: str, ident: str):
    return {"nom": nom, "id": ident, "contenu": ecrits.lire_version(_texte(nom), ident)}


def _texte(nom: str) -> Path:
    """Un texte existant du dossier des procédures, désigné par son seul nom."""
    for p in (config.DATA / "procedures").glob("*.md"):
        if p.name == nom:
            return p
    raise HTTPException(404, "Texte introuvable.")


@app.get("/api/livres/fichier")
def api_fichier(nom: str):
    """Télécharge un livre fabriqué (celui des papiers sort chiffré). Jamais un fichier déposé."""
    chemin = etat.chemin_livre(nom)
    if chemin is None:
        raise HTTPException(404, "Livre introuvable.")
    return FileResponse(chemin, filename=chemin.name)


@app.get("/api/connexions")
def api_connexions():
    cfg = config.load()
    joignable = sync.port_ouvert(cfg)            # l'écran Connexion regarde pour de bon, sans attendre la scrutation
    if joignable != status.read().get("kindle_joignable"):
        status.update(kindle_joignable=joignable, **({"kindle_vu_le": status.now()} if joignable else {}))
    return etat.connexions(cfg, sync.assurer_cle())


@app.get("/api/reglages")
def api_reglages():
    return {**etat.reglages(config.load()), "version": __version__, "lecture_seule": lecture_seule(),
            "journal": journal.lire(60)}


# ================================================================ gestes de l'écran

@app.post("/api/generer")
def api_generer():
    journal.noter("Kit refabriqué")
    _generer(config.load(), forcer=False)       # ne refait que ce qui a changé : les autres livres gardent leur date
    return etat.tuiles(config.load())


@app.post("/api/liseuse/verifier")
def api_verifier():
    """Compare ce qui est sur la liseuse au kit du NAS. N'écrit rien, ni là-bas ni ici."""
    cfg = config.load()
    if not cfg.kindle.host:
        raise HTTPException(409, "L'adresse de la liseuse n'est pas réglée.")
    if not sync.port_ouvert(cfg):
        raise HTTPException(409, "La liseuse ne répond pas : ouvre KOReader et démarre son serveur SSH.")
    try:
        with _TRAVAIL:
            return sync.comparer(cfg)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Lecture de la liseuse impossible ({exc.__class__.__name__}).")


@app.post("/api/livrer")
def api_livrer():
    exiger_ecriture("sur la liseuse")
    cfg = config.load()
    if not sync.port_ouvert(cfg):
        raise HTTPException(409, "La liseuse ne répond pas : ouvre KOReader et démarre son serveur SSH.")
    journal.noter("Kit livré sur la liseuse")
    _session_kindle(cfg)
    return etat.tuiles(config.load())


@app.post("/api/papier/imprime")
def api_papier_imprime():
    journal.noter("Version papier marquée imprimée")
    _papier_imprime()
    return etat.tuiles(config.load())


@app.post("/api/essai")
def api_essai(corps: dict = Body(...)):
    """L'essai en vrai : les quatre points doivent être cochés, sinon rien n'est noté."""
    faits = corps.get("points") or {}
    manquent = [p["texte"] for p in etat.POINTS_ESSAI if not faits.get(p["cle"])]
    if manquent:
        raise HTTPException(422, "L'essai n'est noté que si les quatre points sont faits.")
    cfg = config.load()
    status.update(essai={"le": status.now(), "mot_de_passe": etat.empreinte_mot_de_passe(cfg.papiers_password)})
    journal.noter("Essai du kit fait, les quatre points cochés")
    return etat.tuiles(cfg)


@app.post("/api/disparitions")
def api_disparitions(corps: dict = Body(...)):
    """Le oui demandé avant qu'un livre soit retiré du kit, puis de la liseuse."""
    exiger_ecriture("sur la liseuse")
    en_attente = set(status.read().get("disparitions") or [])
    acceptes = [n for n in corps.get("livres") or [] if n in en_attente]
    if not acceptes:
        raise HTTPException(422, "Aucun de ces livres n'attend d'être retiré.")
    status.update(disparitions_acceptees=acceptes)
    journal.noter(f"{len(acceptes)} livre(s) retiré(s) du kit après confirmation")
    _generer(config.load(), forcer=False)
    return etat.tuiles(config.load())


# ================================================================ écritures dans les sources (2.1.0)
# Chaque route : lecture seule refusée d'abord, puis le verrou (pas d'écriture pendant une fabrication),
# puis l'écriture (qui refuse une seconde fois), puis le journal — sans nom de papier ni de contact.

def _ecrire(quoi: str, faire, *args):
    exiger_ecriture("dans les sources du kit")
    with _TRAVAIL:
        resultat = faire(*args)
    journal.noter(quoi)
    return resultat


async def _corps_brut(request: Request, maxi: int) -> bytes:
    """Le fichier déposé arrive tel quel dans le corps de la requête ; on s'arrête dès qu'il dépasse."""
    annonce = request.headers.get("content-length", "")
    if annonce.isdigit() and int(annonce) > maxi:
        raise ecrits.Refus("Fichier trop lourd.", 413)
    morceaux, total = [], 0
    async for morceau in request.stream():
        total += len(morceau)
        if total > maxi:
            raise ecrits.Refus("Fichier trop lourd.", 413)
        morceaux.append(morceau)
    return b"".join(morceaux)


def _apres() -> dict:
    return api_livres()


@app.put("/api/textes/{nom}")
def api_enregistrer_texte(nom: str, corps: dict = Body(...)):
    _ecrire("Un texte modifié", ecrits.enregistrer_texte, nom, corps.get("contenu"))
    return api_texte(nom)


@app.post("/api/textes")
def api_creer_texte(corps: dict = Body(...)):
    nom = _ecrire("Un texte créé", ecrits.creer_texte, corps.get("titre"), corps.get("numero"))
    return {"nom": nom, **_apres()}


@app.post("/api/textes/{nom}/revenir")
def api_revenir(nom: str, corps: dict = Body(...)):
    _ecrire("Un texte remis à une ancienne version", ecrits.revenir_texte, nom, str(corps.get("version", "")))
    return api_texte(nom)


@app.delete("/api/textes/{nom}")
def api_supprimer_texte(nom: str):
    _ecrire("Un texte supprimé (gardé dans les versions)", ecrits.supprimer_texte, nom)
    return _apres()


@app.post("/api/numeros/{cat}")
def api_ajouter_numero(cat: int, corps: dict = Body(...)):
    _ecrire("Un numéro public ajouté", ecrits.enregistrer_numero, cat, None, corps)
    return _apres()


@app.put("/api/numeros/{cat}/{indice}")
def api_numero(cat: int, indice: int, corps: dict = Body(...)):
    _ecrire("Un numéro public modifié", ecrits.enregistrer_numero, cat, indice, corps)
    return _apres()


@app.post("/api/numeros/{cat}/{indice}/verifie")
def api_numero_verifie(cat: int, indice: int):
    _ecrire("Un numéro public marqué vérifié", ecrits.numero_verifie, cat, indice)
    return _apres()


@app.delete("/api/numeros/{cat}/{indice}")
def api_supprimer_numero(cat: int, indice: int):
    _ecrire("Un numéro public supprimé", ecrits.supprimer_numero, cat, indice)
    return _apres()


@app.put("/api/guides/fichier")
async def api_deposer_guide(request: Request, nom: str, titre: str = "", editeur: str = "", url: str = "",
                            date: str = "", langue: str = ""):
    exiger_ecriture("dans les sources du kit")
    contenu = await _corps_brut(request, ecrits.MAX_GUIDE)
    fiche = {"titre": titre, "editeur": editeur, "url": url, "date": date, "langue": langue}
    _ecrire("Un guide déposé", ecrits.deposer_guide, nom, contenu, fiche)
    return _apres()


@app.put("/api/guides/{indice}/fichier")
async def api_joindre_guide(indice: int, request: Request, nom: str = ""):
    exiger_ecriture("dans les sources du kit")
    contenu = await _corps_brut(request, ecrits.MAX_GUIDE)
    _ecrire("Le fichier d'un guide déposé", ecrits.joindre_guide, indice, nom, contenu)
    return _apres()


@app.put("/api/guides/{indice}")
def api_guide(indice: int, corps: dict = Body(...)):
    _ecrire("La fiche d'un guide modifiée", ecrits.enregistrer_guide, indice, corps)
    return _apres()


@app.delete("/api/guides/{indice}")
def api_retirer_guide(indice: int):
    _ecrire("Un guide retiré (fichier mis de côté)", ecrits.retirer_guide, indice)
    return _apres()


@app.put("/api/papiers")
async def api_deposer_papier(request: Request, nom: str, piece: str | None = None):
    exiger_ecriture("dans les sources du kit")
    contenu = await _corps_brut(request, ecrits.MAX_PAPIER)
    _ecrire("Un papier déposé", ecrits.deposer_papier, nom, contenu, piece)
    return _apres()


@app.post("/api/papiers/conseille")
def api_piece(corps: dict = Body(...)):
    _ecrire("La liste des papiers conseillés réglée", ecrits.ecarter_piece, str(corps.get("cle", "")), bool(corps.get("ecartee")))
    return _apres()


@app.post("/api/papiers/ordre")
def api_ordre(corps: dict = Body(...)):
    _ecrire("L'ordre des papiers changé", ecrits.ordonner_papiers, [str(n) for n in corps.get("noms") or []])
    return _apres()


@app.post("/api/papiers/renommer")
def api_renommer(corps: dict = Body(...)):
    _ecrire("Un papier renommé", ecrits.renommer_papier, str(corps.get("nom", "")), str(corps.get("nouveau", "")))
    return _apres()


@app.post("/api/papiers/retirer")
def api_retirer(corps: dict = Body(...)):
    _ecrire("Un papier retiré du livre (mis de côté)", ecrits.retirer_papier, str(corps.get("nom", "")))
    return _apres()


@app.post("/api/papiers/remettre")
def api_remettre(corps: dict = Body(...)):
    _ecrire("Un papier remis dans le livre", ecrits.remettre_papier, str(corps.get("id", "")))
    return _apres()


@app.post("/api/papiers/effacer")
def api_effacer(corps: dict = Body(...)):
    _ecrire("Un papier mis de côté effacé définitivement", ecrits.effacer_papier, str(corps.get("id", "")))
    return _apres()


@app.put("/api/reglages")
def api_enregistrer_reglages(corps: dict = Body(...)):
    _ecrire("Réglages modifiés", ecrits.enregistrer_reglages, corps)
    return api_reglages()


# ================================================================ interface

@app.get("/{chemin:path}")
def interface(chemin: str):
    if chemin.startswith("api/"):
        raise HTTPException(404, "Adresse inconnue.")
    fichier = (STATIQUE / chemin).resolve() if chemin else None
    if fichier and fichier.is_file() and STATIQUE.resolve() in fichier.parents:
        return FileResponse(fichier)
    index = STATIQUE / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return JSONResponse({"detail": "Interface non compilée."}, status_code=404)
