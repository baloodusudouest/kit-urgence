"""La 2.0.0 : les deux portes, la lecture seule, le contrôle après fabrication, le garde-fou
des disparitions, l'essai, et ce que l'écran lit."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config, controle, generate, main, status, sync

from .conftest import JETON, MDP, brancher_liseuse

PORTEUR = {"Authorization": f"Bearer {JETON}"}


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


# ---------------------------------------------------------------- les deux portes

def test_sans_mot_de_passe_le_kit_ne_demarre_pas(jeu, monkeypatch):
    main.ETAT.clear()
    monkeypatch.setenv("KIT_PASSWORD", "")
    with pytest.raises(SystemExit):
        main.sessions()
    main.ETAT.clear()


def test_l_interface_est_fermee_sans_session(client):
    for chemin in ("/api/etat", "/api/livres", "/api/connexions", "/api/reglages", "/api/textes/10-electricite.md",
                   "/api/livres/fichier?nom=02%20-%20Contacts.epub"):
        assert client.get(chemin).status_code == 401, chemin
    for chemin in ("/api/generer", "/api/livrer", "/api/essai", "/api/papier/imprime", "/api/disparitions",
                   "/api/liseuse/verifier", "/api/deconnexion"):
        assert client.post(chemin, json={}).status_code == 401, chemin
    assert client.get("/api/connexion").status_code == 401          # seule l'écriture du mot de passe est ouverte
    assert client.get("/api/session").json()["connecte"] is False
    assert client.post("/api/connexion", json={"mot_de_passe": "faux"}).status_code == 401


def test_le_jeton_ne_donne_pas_l_interface_et_inversement(ecran):
    assert ecran.get("/api/etat", headers=PORTEUR).status_code == 200      # la session suffit
    assert ecran.post("/generer").status_code == 401                          # la session ne vaut pas jeton
    ecran.cookies.clear()
    assert ecran.get("/api/etat", headers=PORTEUR).status_code == 401      # le jeton ne vaut pas session


def test_jeton_vide_refuse(client, monkeypatch):
    """Avant la 2.0.0, un jeton vide laissait ces adresses ouvertes à tout le réseau."""
    monkeypatch.setenv("API_TOKEN", "")
    for chemin in ("/generer", "/synchroniser", "/papier/imprime"):
        assert client.post(chemin).status_code == 503, chemin
        assert client.post(chemin, headers={"Authorization": "Bearer "}).status_code == 503, chemin


def test_home_assistant_garde_ses_adresses(client):
    etat = client.get("/status").json()
    for cle in ("derniere_generation", "version_nas", "version_kindle", "a_jour", "papier_a_imprimer",
                "kindle_joignable", "derniere_erreur", "avertissements", "livres"):
        assert cle in etat, cle
    assert "01-carte" not in str(etat) and "sources" not in etat          # aucun nom de papier ne sort sans clé
    assert client.post("/generer").status_code == 401
    assert client.post("/generer", headers=PORTEUR).json()["derniere_erreur"] is None
    assert client.post("/synchroniser", headers=PORTEUR).json()["a_jour"] is True
    assert client.post("/papier/imprime", headers=PORTEUR).json()["papier_a_imprimer"] is False
    assert client.get("/health").json()["ok"] is True


def test_deconnexion_ferme_toutes_les_sessions(ecran):
    assert ecran.post("/api/deconnexion").status_code == 200
    assert ecran.get("/api/etat").status_code == 401


# ---------------------------------------------------------------- lecture seule

def test_lecture_seule_refusee_deux_fois(ecran, monkeypatch):
    monkeypatch.setenv("KIT_LECTURE_SEULE", "1")
    avant = len(ecran.liseuse.commandes)
    assert ecran.post("/api/livrer").status_code == 409                       # à l'adresse
    assert ecran.post("/synchroniser", headers=PORTEUR).status_code == 409
    with pytest.raises(Exception, match="lecture seule"):                    # et dans la fonction qui écrit
        sync.livrer(config.load())
    assert len(ecran.liseuse.commandes) == avant                             # aucune commande partie
    assert ecran.post("/api/generer").status_code == 200                      # fabriquer chez soi reste permis
    assert ecran.get("/api/session").json()["lecture_seule"] is True


# ---------------------------------------------------------------- contrôle après fabrication

def test_un_livre_casse_ne_remplace_pas_le_bon(ecran, jeu, monkeypatch):
    bon = (generate.SORTIE / generate.NOM_01).read_bytes()
    texte = jeu / "data" / "procedures" / "10-electricite.md"
    texte.write_text(texte.read_text(encoding="utf-8") + "\nPhrase en plus.\n", encoding="utf-8")
    monkeypatch.setattr(generate, "epub", lambda md, titre, cible, ident: cible.write_bytes(b"pas un livre"))
    etat = ecran.post("/api/generer").json()
    assert (generate.SORTIE / generate.NOM_01).read_bytes() == bon            # l'ancien est toujours là
    assert etat["tuiles"]["erreur"]["nombre"] == 1 and generate.NOM_01 in etat["tuiles"]["erreur"]["lignes"][0]
    assert "problème" in etat["phrase"]
    monkeypatch.undo()
    brancher_liseuse(monkeypatch)
    etat = ecran.post("/api/generer").json()                                  # réparé : il est refait
    assert etat["tuiles"]["erreur"]["nombre"] == 0
    assert (generate.SORTIE / generate.NOM_01).read_bytes() != bon


def test_le_controle_refuse_des_papiers_en_clair_ou_mal_chiffres(jeu, tmp_path):
    generate.generer(config.load())
    livre = generate.SORTIE / generate.NOM_05
    controle.papiers(livre, "papiers-essai", 1)
    with pytest.raises(controle.Echec, match="ne s'ouvre pas"):
        controle.papiers(livre, "un-autre")
    with pytest.raises(controle.Echec, match="manque"):
        controle.papiers(livre, "papiers-essai", 3)
    clair = generate.SORTIE_PAPIER / generate.NOM_PAPIER                      # un PDF sans mot de passe
    with pytest.raises(controle.Echec, match="sans mot de passe"):
        controle.papiers(clair, "papiers-essai")
    vide = tmp_path / "x.epub"
    vide.write_bytes(b"")
    with pytest.raises(controle.Echec):
        controle.verifier("x.epub", vide)


# ---------------------------------------------------------------- garde-fou des disparitions

def test_un_livre_ne_quitte_jamais_la_liseuse_sans_un_oui(ecran, jeu, monkeypatch):
    ecran.post("/api/livrer")
    liseuse = jeu / "liseuse"
    assert (liseuse / generate.NOM_05).exists()
    monkeypatch.setenv("PAPIERS_PASSWORD", "")                                # la variable a sauté de la stack
    etat = ecran.post("/api/generer").json()
    assert etat["tuiles"]["disparition"]["livres"] == [generate.NOM_05]
    ecran.post("/api/livrer")
    assert (liseuse / generate.NOM_05).exists()                               # toujours sur la liseuse
    assert (generate.SORTIE / generate.NOM_05).exists()
    assert ecran.post("/api/disparitions", json={"livres": ["autre.pdf"]}).status_code == 422
    etat = ecran.post("/api/disparitions", json={"livres": [generate.NOM_05]}).json()
    assert etat["tuiles"]["disparition"]["nombre"] == 0
    assert not (generate.SORTIE / generate.NOM_05).exists()
    ecran.post("/api/livrer")
    assert not (liseuse / generate.NOM_05).exists()                           # retiré après le oui


def test_le_livre_revient_si_la_cause_disparait(ecran, monkeypatch):
    monkeypatch.setenv("PAPIERS_PASSWORD", "")
    assert ecran.post("/api/generer").json()["tuiles"]["disparition"]["nombre"] == 1
    monkeypatch.setenv("PAPIERS_PASSWORD", "papiers-essai")
    etat = ecran.post("/api/generer").json()
    assert etat["tuiles"]["disparition"]["nombre"] == 0 and etat["tuiles"]["erreur"]["nombre"] == 0


# ---------------------------------------------------------------- à traiter, essai, papier

def test_les_tuiles_disent_ce_qui_manque(ecran):
    etat = ecran.get("/api/etat").json()
    t = etat["tuiles"]
    assert t["completer"]["nombre"] >= 3 and any(x["ou"] == "numero" for x in t["completer"]["lignes"])
    assert t["verifier"]["nombre"] >= 1
    assert t["guides"]["nombre"] == 3 and "fichier" in t["guides"]["lignes"][0]["manques"]
    assert t["liseuse"]["nombre"] == 1 and t["papier"]["nombre"] == 1 and t["papier"]["changements"] is None
    assert t["essai"]["nombre"] == 1 and "jamais été essayé" in etat["phrase"]
    assert etat["total"] == sum(x["nombre"] for x in t.values())
    assert ecran.get("/status").json()["a_traiter"] == etat["total"]


def test_l_essai_demande_les_quatre_points(ecran, monkeypatch):
    assert ecran.post("/api/essai", json={"points": {"livre": True, "mot_de_passe": True}}).status_code == 422
    tous = {"livre": True, "mot_de_passe": True, "papier": True, "batterie": True}
    etat = ecran.post("/api/essai", json={"points": tous}).json()
    assert etat["tuiles"]["essai"]["nombre"] == 0 and "Dernier essai en vrai" in etat["phrase"]
    monkeypatch.setenv("PAPIERS_PASSWORD", "un-nouveau-mot")                  # le mot de passe change : à réessayer
    essai = ecran.get("/api/etat").json()["tuiles"]["essai"]
    assert essai["nombre"] == 1 and essai["mot_de_passe_change"] is True
    assert "papiers-essai" not in str(status.read()) and "un-nouveau-mot" not in str(status.read())


def test_le_papier_dit_ce_qui_a_change_depuis_l_impression(ecran, jeu):
    etat = ecran.post("/api/papier/imprime").json()
    assert etat["tuiles"]["papier"]["nombre"] == 0
    texte = jeu / "data" / "procedures" / "20-eau.md"
    texte.write_text(texte.read_text(encoding="utf-8") + "\nUne ligne de plus.\n", encoding="utf-8")
    assert ecran.get("/api/etat").json()["tuiles"]["modifie"]["nombre"] == 1
    etat = ecran.post("/api/generer").json()
    assert etat["tuiles"]["papier"]["nombre"] == 1
    assert etat["tuiles"]["papier"]["changements"] == ["Texte « 20-eau »"]


def test_apres_livraison_le_kit_est_a_jour(ecran):
    etat = ecran.post("/api/livrer").json()
    assert etat["tuiles"]["liseuse"]["nombre"] == 0 and "à jour sur la liseuse" in etat["phrase"]
    v = ecran.post("/api/liseuse/verifier").json()
    assert v["differents"] == [] and v["absents"] == [] and len(v["identiques"]) == 4
    ecran.liseuse.joignable = False
    assert ecran.post("/api/livrer").status_code == 409
    assert ecran.post("/api/liseuse/verifier").status_code == 409


def test_verifier_n_ecrit_rien(ecran, jeu):
    ecran.post("/api/livrer")
    (jeu / "liseuse" / generate.NOM_02).write_bytes(b"abime")
    avant = {p.name: p.read_bytes() for p in (jeu / "liseuse").iterdir()}
    v = ecran.post("/api/liseuse/verifier").json()
    assert v["differents"] == [generate.NOM_02]
    assert {p.name: p.read_bytes() for p in (jeu / "liseuse").iterdir()} == avant


# ---------------------------------------------------------------- livres, contacts, papiers

def test_l_ecran_des_livres(ecran):
    d = ecran.get("/api/livres").json()
    assert [l["numero"] for l in d["livres"]] == ["00", "01", "02", "05", "A4"]
    assert all(l["present"] and l["poids"] > 0 and not l["echec"] for l in d["livres"])
    assert [c["nom"] for c in d["contacts"]] == ["Camille Voisin", "Plomberie du Coteau"]
    assert d["contacts"][0]["carnet"] is None                                # pas d'adresse de carnet réglée
    assert d["papiers"] == [{"nom": "01-carte.png", "poids": d["papiers"][0]["poids"]}]
    assert [t["nom"] for t in d["textes"]][:2] == ["00-lisez-moi.md", "10-electricite.md"]
    assert "lectricit" in ecran.get("/api/textes/10-electricite.md").json()["contenu"]
    assert ecran.get("/api/textes/..%2Fconfig%2Fconfig.yaml").status_code in (404, 401)


def test_lien_vers_carnet(ecran, monkeypatch):
    monkeypatch.setenv("KIT_CARNET_URL", "http://nas.exemple:8096/")
    c = ecran.get("/api/livres").json()["contacts"][0]
    assert c["carnet"] == "http://nas.exemple:8096/#/contacts/uid-voisine"


def test_on_telecharge_les_livres_fabriques_et_rien_d_autre(ecran):
    r = ecran.get("/api/livres/fichier", params={"nom": generate.NOM_05})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-" and b"/Encrypt" in r.content
    assert ecran.get("/api/livres/fichier", params={"nom": generate.NOM_PAPIER}).status_code == 200
    for nom in ("01-carte.png", "../../papiers/01-carte.png", "manifest.json", "../../config/config.yaml"):
        assert ecran.get("/api/livres/fichier", params={"nom": nom}).status_code == 404, nom


def test_connexions_et_reglages(ecran):
    c = ecran.get("/api/connexions").json()
    assert c["liseuse"]["reglee"] and c["liseuse"]["cle_publique"].startswith("ssh-ed25519 ")
    assert c["carnet"]["nombre"] == 2 and c["home_assistant"]["jeton_regle"] is True
    ecran.post("/generer", headers=PORTEUR)
    assert ecran.get("/api/connexions").json()["home_assistant"]["dernier_appel"]
    r = ecran.get("/api/reglages").json()
    assert r["titre_foyer"] == "Maison des Tilleuls" and r["mot_de_passe_papiers"] is True
    assert "papiers-essai" not in str(r)
    assert any("refabriqué" in l["quoi"] for l in r["journal"])
