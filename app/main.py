"""Kit d'urgence : générateur, livraison vers la liseuse, et (2.0.0) interface.

Deux portes, deux clés :
- l'interface et `/api/…` : mot de passe commun (MAISON_PASSWORD seul depuis la 2.5), session par cookie ;
- `/generer`, `/synchroniser`, `/papier/imprime`, `/cle-publique` : jeton de Home Assistant (API_TOKEN) ;
  le jeton commun de la maison (MAISON_JETON, MAISON_JETON_ANCIEN) y est accepté en plus, pour carnet.
  API_TOKEN reste obligatoire tant que Home Assistant s'en sert : sans lui ces adresses refusent (503),
  même si MAISON_JETON est posé. Un jeton vide ne vaut jamais « ouvert à tous ».
- `/externe/sauvegarde` (2.5) : jeton commun seul (MAISON_JETON), pour l'Anneau ; MAISON_JETON vide = 404.
Sans clé : `/health` et `/status` (lu par les capteurs de Home Assistant ; aucun nom de papier dedans).
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import os
import threading
import time
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from . import __version__, config, ecrits, etat, generate, journal, maison, sauvegarde, status, sync
from .auth import COMMUN, DUREE, Sessions, en_https
from .garde import LectureSeule, exiger_ecriture, lecture_seule, origine as origine_lecture_seule

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kit")
for bavard in ("weasyprint", "fontTools"):
    logging.getLogger(bavard).setLevel(logging.ERROR)

_TRAVAIL = threading.Lock()  # une seule génération / livraison à la fois
STATIQUE = Path(__file__).parent / "static"
GENERATION = config.STATE / "session_generation"
ETAT: dict = {}
# 2.4 : la page a-t-elle été ouverte par le réseau privé (Tailscale) ? Posé à chaque requête par la garde,
# lu pour choisir l'adresse de carnet donnée au navigateur.
_PRIVE: contextvars.ContextVar[bool] = contextvars.ContextVar("prive", default=False)

app = FastAPI(title="kit-urgence", version=__version__, docs_url=None, redoc_url=None)

# 2.6.0 : tâches de fond suivies dans /health (maison.TACHES, socle 0.9.0 ; un seul worker uvicorn).
TACHE_SCRUTATION = "scrutation"     # régulière : recherche de la liseuse, toutes les scrutation_secondes (15 s au moins)
TACHE_FABRICATION = "fabrication"   # à la demande : fabrication des livres
TACHE_LIVRAISON = "livraison"       # à la demande : envoi des livres sur la liseuse
maison.TACHES.declarer(TACHE_FABRICATION, type="demande")
maison.TACHES.declarer(TACHE_LIVRAISON, type="demande")


def jeton() -> str:
    """Jeton de Home Assistant (API_TOKEN). Obligatoire : sans lui, les adresses à jeton restent fermées."""
    return os.environ.get("API_TOKEN", "")


def jetons_acceptes() -> tuple[str, ...]:
    """2.4 : API_TOKEN (Home Assistant, et carnet tant qu'il l'envoie), puis le jeton commun de la maison
    (MAISON_JETON, MAISON_JETON_ANCIEN) pour carnet."""
    return tuple(j for j in (jeton(), *maison.jetons()) if j)


def sessions() -> Sessions:
    if "sessions" not in ETAT:
        mdp = config.mot_de_passe()
        if len(mdp) < 12:
            raise SystemExit("MAISON_PASSWORD est absent ou trop court (12 caractères au moins) : "
                             "le kit d'urgence ne démarre pas.")
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
    _PRIVE.set(maison.est_prive(request.headers.get("host", "")))
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


def _auth(request: Request) -> None:
    """Jeton de Home Assistant et de carnet. Vide = refusé (avant la 2.0.0 : ouvert à tous).
    2.4 : API_TOKEN ou MAISON_JETON (comparaison en temps constant) ; API_TOKEN reste obligatoire
    tant que Home Assistant s'en sert : sans lui, refus même avec MAISON_JETON."""
    if not jeton():
        raise HTTPException(503, "Jeton non réglé : définis KIT_API_TOKEN dans la stack.")
    if not maison.jeton_valide(maison.jeton_propose(request.headers), jetons_acceptes()):
        raise HTTPException(401, "Jeton invalide")
    status.update(dernier_appel_jeton=status.now())


# ================================================================ travail

def _generer_si_besoin(cfg: config.Config, forcer: bool = False) -> None:
    e = status.read()
    if forcer or not e.get("version_nas") or e.get("sources") != generate.sha_sources(cfg):
        log.info("Génération du kit…")
        with maison.TACHES.tour(TACHE_FABRICATION):
            generate.generer(cfg)


def _generer(cfg: config.Config, forcer: bool = True) -> dict:
    with _TRAVAIL:
        try:
            with maison.TACHES.tour(TACHE_FABRICATION):
                return generate.generer(cfg, forcer=forcer)
        except Exception as exc:  # noqa: BLE001 — l'erreur est montrée à l'écran et à Home Assistant
            log.exception("Échec de la génération")
            return status.update(derniere_erreur=f"{status.now()} : {exc}")


def _session_kindle(cfg: config.Config) -> dict:
    """Régénère si les sources ont changé, puis livre et vérifie."""
    with _TRAVAIL:
        try:
            _generer_si_besoin(cfg)
            exiger_ecriture("sur la liseuse")    # 2.6.0 : un refus (lecture seule) n'est pas une livraison ratée
            with maison.TACHES.tour(TACHE_LIVRAISON):
                return sync.livrer(cfg)
        except LectureSeule:
            raise
        except Exception as exc:  # noqa: BLE001 — l'erreur est remontée à HA
            log.exception("Échec de la livraison")
            return status.update(derniere_erreur=f"{status.now()} : {exc}")


def _periode_scrutation(cfg: config.Config) -> int:
    return max(15, cfg.scrutation_secondes)


def _tour_de_scrutation(cfg: config.Config, memoire: dict) -> None:
    """Un tour de scrutation. 2.6.0 : la détection est suivie comme tâche régulière « scrutation » ; la
    livraison qui peut suivre a sa propre tâche (« livraison ») : un envoi long ne fait pas croire à un blocage.
    `memoire` garde d'un tour à l'autre `deja_livre` et `dernier_vu`."""
    maison.TACHES.declarer(TACHE_SCRUTATION, _periode_scrutation(cfg))   # l'intervalle se change dans Réglages
    try:
        with maison.TACHES.tour(TACHE_SCRUTATION):
            joignable = sync.port_ouvert(cfg)
            if joignable != status.read().get("kindle_joignable"):
                status.update(kindle_joignable=joignable)
                log.info("Liseuse %s", "joignable" if joignable else "hors ligne")
            if joignable and time.monotonic() - memoire["dernier_vu"] > 3600:   # « vue le » : une écriture par heure au plus
                status.update(kindle_vu_le=status.now())
                memoire["dernier_vu"] = time.monotonic()
        if joignable and not memoire["deja_livre"] and not lecture_seule():
            e = _session_kindle(cfg)
            memoire["deja_livre"] = e.get("derniere_erreur") is None
        if not joignable:
            memoire["deja_livre"] = False
    except Exception:  # noqa: BLE001
        log.exception("Erreur de scrutation")


def _scrutation() -> None:
    """Détecte l'apparition de la liseuse (port SSH ouvert) et livre une fois par présence."""
    memoire = {"deja_livre": False, "dernier_vu": 0.0}
    while True:
        cfg = config.load()
        _tour_de_scrutation(cfg, memoire)
        time.sleep(_periode_scrutation(cfg))


@app.on_event("startup")
def _demarrage() -> None:
    try:                                   # 2.5.4 : réordonnancement des papiers coupé par un arrêt
        n = ecrits.reprendre_ordre_interrompu()
        if n:
            log.warning("%s papier(s) remis sous leur nom après un réordonnancement interrompu", n)
    except OSError:
        log.exception("Reprise du réordonnancement des papiers impossible")
    sessions()                                   # refuse de démarrer sans mot de passe
    try:                                   # 2.5.7 (M45) : anciennes empreintes rapides réécrites une fois
        n = generate.reprendre_empreintes_anciennes(config.load())
        if n:
            log.info("%s empreinte(s) du mot de passe des papiers réécrite(s) en empreinte lente", n)
    except Exception:  # noqa: BLE001 — au pire, le livre des papiers est refait une fois
        log.exception("Reprise des anciennes empreintes impossible")
    if not jeton():
        log.warning("API_TOKEN est vide : Home Assistant et carnet ne pourront rien lancer "
                    "(MAISON_JETON seul ne suffit pas, API_TOKEN reste obligatoire).")
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
        maison.TACHES.declarer(TACHE_SCRUTATION, _periode_scrutation(cfg))
        threading.Thread(target=_scrutation, daemon=True, name="scrutation").start()


# ================================================================ sans clé

def _session_ok(request: Request) -> bool:
    try:
        return sessions().connecte(request.cookies)
    except SystemExit:                   # mot de passe absent : l'appli n'aurait pas démarré
        return False


# ================================================================ fiches « Connexion » (2.7.0, contrat 3, socle 0.11.0)
# Les services du kit, au format commun (maison.Services) : GET /api/maison/services, POST …/{id}/verifier.
# Textes « lit » et « écrit » repris de l'ancien écran (pages/Services.svelte, retiré). « Vérifier » n'écrit jamais
# chez le service ; « Livrer » (POST /api/livrer, route existante) est le geste de la fiche Liseuse.
# L'adresse, le port et le dossier de la liseuse ne sont pas dans la stack : ils se règlent dans Réglages.

def _quand(iso: str | None) -> str:
    """« le 18/11/2026 à 14:05 » (heure du conteneur), « jamais » sans date."""
    if not iso:
        return "jamais"
    try:
        from datetime import datetime
        d = datetime.fromisoformat(str(iso)).astimezone()
    except ValueError:
        return str(iso)
    return d.strftime("le %d/%m/%Y à %H:%M")


def _essai_liseuse() -> tuple[bool, str]:
    """Le port SSH de KOReader répond-il ? Si oui, relit les empreintes des livres du kit sur la liseuse et les
    compare au NAS (sync.comparer, la vérification de toujours) : rien n'est écrit sur la liseuse. Pendant une
    fabrication ou une livraison, la comparaison n'est pas lancée (on n'attend pas le verrou)."""
    cfg = config.load()
    joignable = sync.port_ouvert(cfg)
    if joignable != status.read().get("kindle_joignable"):      # comme l'ancien écran : l'état suit l'essai
        status.update(kindle_joignable=joignable, **({"kindle_vu_le": status.now()} if joignable else {}))
    if not joignable:
        return False, "La liseuse ne répond pas : ouvre KOReader et démarre son serveur SSH."
    if not _TRAVAIL.acquire(blocking=False):
        return True, "Elle répond. Une fabrication ou une livraison est en cours : comparaison à refaire ensuite."
    try:
        r = sync.comparer(cfg)
    finally:
        _TRAVAIL.release()
    ecarts = [f"Différents : {', '.join(r['differents'])}." if r["differents"] else "",
              f"Absents de la liseuse : {', '.join(r['absents'])}." if r["absents"] else "",
              f"Sur la liseuse mais plus dans le kit : {', '.join(r['en_trop'])}." if r["en_trop"] else ""]
    if not r["differents"] and not r["absents"]:
        return True, " ".join(x for x in [f"{len(r['identiques'])} livre(s) identiques : la liseuse a bien le kit "
                                           "du NAS.", *ecarts] if x)
    return True, " ".join(x for x in [f"{len(r['identiques'])} livre(s) identiques.", *ecarts] if x)


def _essai_carnet() -> tuple[bool, str]:
    """Lecture locale seulement : le fichier de contacts déposé par carnet (le kit ne joint pas carnet)."""
    c = etat.connexions(config.load(), "", prive=False)["carnet"]
    if not c["present"]:
        return False, "Aucun contact reçu : carnet n'a encore rien déposé."
    return True, f"{c['nombre']} contact(s) reçus {_quand(c['recus_le'])}."


def _essai_home_assistant() -> tuple[bool, str]:
    """Rien n'est demandé à Home Assistant (c'est lui qui appelle le kit) : on dit son dernier appel."""
    dernier = status.read().get("dernier_appel_jeton")
    if not dernier:
        return True, "Jeton réglé dans la stack ; aucun appel avec jeton noté pour l'instant."
    return True, f"Jeton réglé dans la stack ; dernier appel avec jeton {_quand(dernier)}."


def _guide_liseuse() -> dict:
    """Marche à suivre de la fiche Liseuse (appareil qu'on allume soi-même), reprise de l'ancien écran Connexion,
    d'À traiter, du README, du livre 00 et du paquet Home Assistant. Ni utilisateur SSH ni mot de passe."""
    cfg = config.load()
    e = status.read()
    secondes = _periode_scrutation(cfg)
    return {
        "reglages": [
            {"nom": "Adresse", "valeur": f"{cfg.kindle.host}:{cfg.kindle.port}" if cfg.kindle.host
             else "pas réglée (Réglages › Adresse de la liseuse)"},
            {"nom": "Dossier des livres", "valeur": cfg.kindle.dossier},
            {"nom": "Recherche de la liseuse", "valeur": f"toutes les {secondes} secondes (Réglages)"},
            {"nom": "Vue", "valeur": _quand(e.get("kindle_vu_le"))},
            {"nom": "Dernière livraison", "valeur": _quand(e.get("derniere_livraison"))},
            {"nom": "Kit dessus", "valeur": "le même que sur le NAS" if e.get("a_jour")
             else "plus ancien que celui du NAS"},
        ],
        "allumer": [
            "Charger la liseuse et désactiver le mode avion.",
            "Allumer la liseuse et ouvrir KOReader (dans la bibliothèque : KUAL, puis KOReader, puis Start KOReader).",
            "Activer le Wi-Fi, puis dans le menu Outils › Plus d'outils › SSH, démarrer le serveur SSH "
            "(Réseau › Serveur SSH › Démarrer selon la version de KOReader).",
            f"La laisser allumée une minute : le kit la cherche toutes les {secondes} secondes, la voit et livre tout "
            "seul ce qui a changé, puis relit chaque livre sur la liseuse pour vérifier. Home Assistant confirme par "
            "« Kit d'urgence à jour sur le Kindle ».",
            "Ensuite : couper le serveur SSH dans KOReader et remettre le mode avion.",
        ],
        "pannes": [
            {"signe": "« Pas relié » : l'adresse de la liseuse n'est pas réglée",
             "faire": ["Dans Réglages : adresse de la liseuse (IP fixe), port SSH (2222 pour le serveur SSH de "
                       "KOReader) et dossier des livres sur la liseuse."],
             "commandes": []},
            {"signe": "« Ne répond pas » : la liseuse ne répond pas",
             "faire": ["Est-elle allumée, KOReader ouvert, Wi-Fi activé, hors mode avion ? Le serveur SSH de KOReader "
                       "est-il démarré ?",
                       "L'adresse réglée est-elle toujours la sienne ? Sinon la corriger dans Réglages, ou réserver son "
                       "adresse dans la box (bail DHCP statique).",
                       "Pas vue depuis deux mois : elle est peut-être déchargée (À traiter le signale)."],
             "commandes": []},
            {"signe": "Elle répond, mais « Vérifier » ou « Livrer » échoue (lecture impossible)",
             "faire": ["La clé du kit est-elle autorisée sur la liseuse ? Voir « Installation (une seule fois) ».",
                       "La clé d'hôte de la liseuse est épinglée à la première connexion (fichier known_hosts du "
                       "dossier d'état, KIT_STATE_DIR) : si KOReader ou la liseuse a été réinstallé, elle a changé et "
                       "la connexion est refusée."],
             "commandes": []},
            {"signe": "Livraison refusée : dossier trop large",
             "faire": ["La livraison effacerait des livres qui ne sont pas au kit. Choisir un dossier à lui "
                       "(ex. /mnt/us/documents/Urgence) dans Réglages."],
             "commandes": []},
            {"signe": "La liseuse s'endort pendant l'envoi",
             "faire": ["Un livre arrivé incomplet est effacé et l'ancien reste. La garder allumée, puis relancer "
                       "« Livrer »."],
             "commandes": []},
            {"signe": "« Livrer » reste grisé",
             "faire": ["Mode lecture seule : le kit fabrique ses livres mais n'écrit ni sur la liseuse ni dans ses "
                       "sources. À retirer dans la stack (KIT_LECTURE_SEULE, ou MAISON_LECTURE_SEULE pour toute la "
                       "maison) quand tout va bien."],
             "commandes": []},
            {"signe": "Plan B : serveur SSH hors service",
             "faire": ["Copier le contenu de output/Urgence/ (dossier de données du kit) dans documents/Urgence/ du "
                       "Kindle par USB. Les PDF s'ouvrent aussi sans KOReader ; les EPUB nécessitent KOReader."],
             "commandes": []},
        ],
        "une_fois": [
            {"texte": "Prérequis : un Kindle jailbreaké, avec KOReader (lancé depuis KUAL).", "commande": ""},
            {"texte": "Kindle branché en USB, KOReader fermé, ajouter la clé du kit (la ligne ci-dessous) dans le "
                      "fichier koreader/settings/SSH/authorized_keys de la liseuse.",
             "commande": sync.assurer_cle()},
            {"texte": "Donner à la liseuse une adresse fixe dans la box (bail DHCP statique), puis la noter dans "
                      "Réglages avec le port SSH de KOReader (2222) et un dossier à lui "
                      "(ex. /mnt/us/documents/Urgence).", "commande": ""},
        ],
        "note": "Rappel de Home Assistant le 1er du mois et en vigilance orange ou rouge. Le kit ne retire jamais "
                "seul un livre de la liseuse : il attend un oui dans À traiter.",
    }


SERVICES = maison.Services(sauvegarde.APPLI)
SERVICES.ajouter(
    "liseuse", "Liseuse",
    lit="Le kit n'y lit que les empreintes de ses propres livres : « Vérifier » relit chaque livre sur la liseuse et "
        "le compare à celui du NAS, sans rien écrire.",
    ecrit="Le kit y écrit ses livres, dans son dossier de la liseuse, par le serveur SSH de KOReader. « Livrer » "
          "envoie ce qui diffère, puis relit chaque livre sur la liseuse pour vérifier.",
    regle=lambda: bool(config.load().kindle.host),
    reglage="Aucune variable : l'adresse de la liseuse se règle dans Réglages",
    essai=_essai_liseuse, geste={"id": "livrer", "nom": "Livrer"},
    derniere_ecriture=lambda: status.read().get("derniere_livraison"), guide=_guide_liseuse)
SERVICES.ajouter(
    "carnet", "carnet", genre="maison", cible="carnet",
    lit="Le kit ne lit pas carnet : c'est carnet qui dépose ici les contacts du groupe Urgence, puis demande une "
        "fabrication.",
    ecrit="Rien : le kit n'écrit rien dans carnet.",
    regle=lambda: bool(jeton()), reglage="KIT_API_TOKEN",
    essai=_essai_carnet)
SERVICES.ajouter(
    "home-assistant", "Home Assistant",
    lit="Le kit ne lit rien chez lui : Home Assistant lit l'état du kit sans clé (/status), et lance fabrication, "
        "livraison et « papier imprimé » avec un jeton (/generer, /synchroniser, /papier/imprime).",
    ecrit="Rien : le kit ne lui écrit rien.",
    regle=lambda: bool(jeton()), reglage="KIT_API_TOKEN",
    essai=_essai_home_assistant)
# Monté APRÈS la garde : le dernier middleware ajouté passe en premier (sinon la garde refuserait l'Anneau).
maison.monter_services(app, SERVICES, _session_ok)


@app.get("/health")
def health(request: Request) -> dict:
    """2.6.0 : + version_socle, taches, copie_base (null : le kit n'a pas de base SQLite) ; messages d'erreur
    des tâches seulement avec le jeton commun (MAISON_JETON) ou une session."""
    return {"ok": True, "version": __version__,
            **maison.sante(request, jeton_commun=maison.jetons(), session_ok=_session_ok(request))}


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
            "lecture_seule": lecture_seule(), "lecture_seule_origine": origine_lecture_seule()}


@app.post("/api/connexion")
async def connexion(request: Request, corps: dict = Body(...)):
    s = sessions()
    if not os.environ.get("KIT_SANS_ATTENTE"):
        await asyncio.sleep(s.attente())
    if not s.verifier_mot_de_passe(str(corps.get("mot_de_passe", ""))):
        raise HTTPException(401, "Mot de passe incorrect.")
    r = JSONResponse({"ok": True})
    r.set_cookie(s.cookie, s.creer(), max_age=DUREE, httponly=True, samesite="strict", secure=en_https(request))
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
            **etat.liste_contacts(cfg, prive=_PRIVE.get())}


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
    """Ancien écran Connexion (retiré en 2.7.0, remplacé par /api/maison/services). À retirer à la version suivante."""
    cfg = config.load()
    joignable = sync.port_ouvert(cfg)            # l'écran Connexion regarde pour de bon, sans attendre la scrutation
    if joignable != status.read().get("kindle_joignable"):
        status.update(kindle_joignable=joignable, **({"kindle_vu_le": status.now()} if joignable else {}))
    return etat.connexions(cfg, sync.assurer_cle(), prive=_PRIVE.get())


@app.get("/api/reglages")
def api_reglages():
    return {**etat.reglages(config.load()), "version": __version__, "lecture_seule": lecture_seule(),
            "lecture_seule_origine": origine_lecture_seule(), "journal": journal.lire(60),
            "sauvegarde_possible": bool(maison.jetons())}


# ================================================================ gestes de l'écran

@app.post("/api/generer")
def api_generer():
    journal.noter("Kit refabriqué")
    _generer(config.load(), forcer=False)       # ne refait que ce qui a changé : les autres livres gardent leur date
    return etat.tuiles(config.load())


@app.post("/api/liseuse/verifier")
def api_verifier():
    """Compare ce qui est sur la liseuse au kit du NAS. N'écrit rien, ni là-bas ni ici.
    Ancien écran Connexion : depuis la 2.7.0, « Vérifier » de la fiche Liseuse fait la même comparaison
    (POST /api/maison/services/liseuse/verifier). À retirer à la version suivante."""
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
    e = _session_kindle(cfg)
    ok = not e.get("derniere_erreur")       # 2.7.0 : le geste de la fiche Liseuse sert aussi d'essai
    SERVICES.noter("liseuse", ok, "Livraison faite et vérifiée." if ok else "Livraison ratée.")
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
def api_enregistrer_reglages(corps=Body(...)):
    """Réglages du kit. 2.5.1 (choix de Julien) : refusés en lecture seule, comme avant la 2.5.
    Mauvais type → 400, hors bornes → 422."""
    exiger_ecriture("dans les réglages du kit")
    with _TRAVAIL:
        ecrits.enregistrer_reglages(corps)
    journal.noter("Réglages modifiés")
    return api_reglages()


# ================================================================ sauvegarde chez l'Anneau (2.5, contrat 1)

@app.get("/externe/sauvegarde")
def externe_sauvegarde(request: Request):
    """Lue chaque nuit par l'Anneau, avec le jeton commun (API_TOKEN n'ouvre pas cette porte).
    Réglages d'usage et version seulement : ni papier, ni clé SSH, ni mot de passe, ni variable."""
    acceptes = maison.jetons()
    if not acceptes:
        raise HTTPException(404, "Not Found")                 # MAISON_JETON vide : porte fermée
    if not maison.jeton_valide(maison.jeton_propose(request.headers), acceptes):
        raise HTTPException(401, "Jeton commun manquant ou invalide.")
    return maison.sauvegarde(sauvegarde.APPLI, __version__, sauvegarde.actuels(config.load()),
                             exclus=sauvegarde.EXCLUS)


# Pour les tests : un faux Anneau (fonction (adresse, jeton) → dict) remplace la demande HTTP
LIRE_ANNEAU = None


def _demander_anneau(le: str = "") -> dict:
    """Demande à l'Anneau ; ses pannes deviennent des messages clairs (404 rien à restaurer, 503 injoignable)."""
    if le and not sauvegarde.JOUR.match(le):
        raise HTTPException(400, "Date attendue sous la forme AAAA-MM-JJ.")
    if not maison.jeton_a_envoyer():
        raise HTTPException(503, "Jeton commun absent (MAISON_JETON) : l'Anneau ne peut pas être interrogé.")
    try:
        reponse = maison.lire_sauvegarde(sauvegarde.APPLI, le, lire=LIRE_ANNEAU)
    except Exception as exc:                                  # noqa: BLE001 — urllib, réseau, JSON…
        if getattr(exc, "code", None) == 404:
            raise HTTPException(404, "L'Anneau n'a aucune sauvegarde du kit"
                                     f"{' le ' + le if le else ''}.") from exc
        raise HTTPException(503, "L'Anneau ne répond pas : restauration impossible pour l'instant "
                                 f"({exc.__class__.__name__}).") from exc
    if not isinstance(reponse, dict):
        raise HTTPException(503, "Réponse de l'Anneau illisible.")
    if le and not isinstance(reponse.get("reglages"), dict):
        raise HTTPException(404, f"L'Anneau n'a aucune sauvegarde du kit le {le}.")
    return reponse


@app.get("/api/restaurer")
def api_restaurer_voir(le: str = ""):
    if not le:
        dates = _demander_anneau().get("dates") or []
        return {"dates": [d for d in dates if isinstance(d, str)]}
    sauve = _demander_anneau(le)
    return {"le": le, "version": sauve.get("version", ""),
            "differences": maison.differences(sauvegarde.actuels(config.load()), sauve["reglages"],
                                              sauvegarde.EXCLUS)}


@app.post("/api/restaurer")
def api_restaurer(corps: dict = Body(...)):
    """Applique les réglages d'une sauvegarde qui diffèrent d'aujourd'hui. Refusé en lecture seule (2.5.1,
    choix de Julien). Les valeurs passent par les mêmes contrôles que l'écran."""
    exiger_ecriture("dans les réglages du kit")
    le = str(corps.get("le", ""))
    if not le:
        raise HTTPException(400, "Choisis la date de la sauvegarde à restaurer.")
    sauve = _demander_anneau(le)
    actuels = sauvegarde.actuels(config.load())
    diffs = maison.differences(actuels, sauve["reglages"], sauvegarde.EXCLUS)
    if diffs:
        nouveaux = {**actuels, **{d["cle"]: d["sauve"] for d in diffs}}
        try:
            with _TRAVAIL:
                ecrits.enregistrer_reglages(sauvegarde.corps_ecran(nouveaux))
        except ecrits.Refus as exc:
            raise HTTPException(422, f"Sauvegarde du {le} non appliquée : {exc}") from exc
    journal.noter(f"Réglages restaurés depuis la sauvegarde du {le} ({len(diffs)} changé(s))")
    return {"le": le, "appliques": [d["cle"] for d in diffs], **api_reglages()}


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
