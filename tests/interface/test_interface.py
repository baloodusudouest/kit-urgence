"""Tests d'écran du kit, sur PC et sur iPhone, contre un jeu inventé et une fausse liseuse."""
from __future__ import annotations

import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
RACINE = Path(__file__).resolve().parents[2]
MDP = "mot-de-passe-essai"


@pytest.fixture(scope="module")
def adresse():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "tests.interface.serveur", str(port)], cwd=RACINE,
                            stdout=subprocess.PIPE, text=True)
    base = f"http://127.0.0.1:{port}"
    for _ in range(300):
        try:
            if urllib.request.urlopen(base + "/health", timeout=1).status == 200:
                break
        except OSError:
            time.sleep(0.1)
    else:
        proc.terminate()
        pytest.fail("Le kit de démonstration n'a pas démarré.")
    yield base
    proc.terminate()


@pytest.fixture(scope="module")
def navigateur():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture(params=["pc", "iphone"])
def page(request, navigateur, adresse):
    mobile = request.param == "iphone"
    ctx = navigateur.new_context(viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 860},
                                 is_mobile=mobile, has_touch=mobile)
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.mobile = mobile
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(adresse)
    pg.get_by_label(re.compile("Mot de passe")).fill(MDP)
    pg.get_by_role("button", name="Se connecter").click()
    pg.locator("#phrase").wait_for()
    yield pg
    assert not erreurs, erreurs
    ctx.close()


def aller(page, nom):
    page.locator(f"nav a[aria-label^='{nom}']").click()
    page.get_by_role("heading", level=1, name=nom).wait_for()


def tuile(page, nom):
    return page.locator("button", has=page.locator(".nom-tuile", has_text=re.compile(f"^{re.escape(nom)}$")))


def test_mauvais_mot_de_passe(navigateur, adresse):
    pg = navigateur.new_page()
    pg.goto(adresse)
    pg.get_by_label(re.compile("Mot de passe")).fill("faux")
    pg.get_by_role("button", name="Se connecter").click()
    pg.get_by_role("alert").wait_for()
    assert pg.locator("#phrase").count() == 0
    pg.close()


def test_l_ouverture_dit_l_etat_et_ce_qui_manque(page):
    assert "essayé" in page.locator("#phrase").inner_text()
    for nom in ("Essai du kit", "À compléter", "Numéros à vérifier", "Guides incomplets"):
        assert tuile(page, nom).count() == 1, nom
    assert tuile(page, "Erreur").count() == 0                       # une tuile à zéro s'efface
    tuile(page, "Guides incomplets").click()
    assert "il manque" in page.get_by_role("region", name="Guides incomplets").inner_text()


def test_rien_ne_deborde_et_les_boutons_se_touchent(page):
    for nom in ("À traiter", "Kit", "Connexion", "Réglages"):
        aller(page, nom)
        largeur = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        assert largeur[0] <= largeur[1], (nom, largeur)
        if page.mobile:
            petits = page.evaluate("""() => [...document.querySelectorAll('main button, nav a')]
                .filter(e => e.offsetParent && (e.getBoundingClientRect().height < 36)).map(e => e.textContent.trim())""")
            assert not petits, (nom, petits)


def test_noter_l_essai_demande_les_quatre_points(page):
    tuile(page, "Essai du kit").click()
    noter = page.get_by_role("button", name="Noter l'essai")
    assert noter.is_disabled()
    cases = page.get_by_role("checkbox")
    assert cases.count() == 4
    for i in range(3):
        cases.nth(i).check()
    assert noter.is_disabled()


def test_les_papiers_ne_montrent_que_des_noms(page):
    aller(page, "Kit")
    page.get_by_role("button", name=re.compile("Papiers")).click()
    liste = page.get_by_role("list", name="Papiers")
    assert "01-carte.png" in liste.inner_text()
    assert page.locator("main img").count() == 0                    # aucun aperçu
    lien = page.get_by_role("link", name=re.compile("Télécharger"))
    assert "chiffré" in lien.inner_text() and "Papiers" in lien.get_attribute("href")


def test_les_contacts_se_lisent_et_les_textes_s_ouvrent(page):
    aller(page, "Kit")
    page.get_by_role("button", name=re.compile("^Contacts")).click()
    contacts = page.get_by_role("list", name="Contacts").inner_text()
    assert "Camille Voisin" in contacts and "06 00 00 00 02" in contacts
    page.get_by_role("button", name=re.compile("^Procédures")).click()
    page.get_by_role("list", name="Textes").get_by_role("button").first.click()
    page.locator("textarea").wait_for()
    assert len(page.locator("textarea").input_value()) > 100




# ---------------------------------------------------------------- 2.1.0 : écrire depuis l'écran
# Ces tests changent le jeu : ils viennent après ceux qui le lisent, et chacun défait ce qu'il a fait
# ou travaille sur un objet qu'il crée.

def ouvrir_livre(page, nom):
    aller(page, "Kit")
    page.locator("li > button", has_text=re.compile(nom)).first.click()


def test_ecrire_un_texte_et_revenir_a_l_ancien(page):
    ouvrir_livre(page, "Procédures")
    page.get_by_role("list", name="Textes").get_by_role("button", name=re.compile("^Eau")).click()
    zone = page.locator("textarea")
    zone.wait_for()
    avant = zone.input_value()
    enregistrer = page.get_by_role("button", name="Enregistrer")
    assert enregistrer.is_disabled()                                # rien n'a changé : rien à enregistrer
    marque = "Ligne ajoutée pendant l'essai " + ("iPhone" if page.mobile else "PC")
    zone.fill(avant + "\n" + marque + "\n")
    enregistrer.click()
    page.get_by_role("status").filter(has_text="Enregistré").wait_for()
    versions = page.get_by_role("list", name="Versions")
    versions.get_by_role("button", name="Revenir à cette version").first.click()
    page.get_by_role("status").filter(has_text="Ancienne version remise").wait_for()
    assert marque not in zone.input_value()


def test_deposer_ranger_retirer_remettre_un_papier(page, tmp_path):
    ouvrir_livre(page, "Papiers")
    nom = "permis-iphone.png" if page.mobile else "permis-pc.png"
    from tests.conftest import PNG
    fichier = tmp_path / nom
    fichier.write_bytes(PNG)
    page.locator("input[type=file][aria-label='Déposer des papiers']").set_input_files(str(fichier))
    page.locator("#message-papiers", has_text="déposé").wait_for()
    liste = page.get_by_role("list", name="Papiers", exact=True)
    assert nom.split(".")[0] in liste.inner_text()
    assert page.locator("main img").count() == 0                    # toujours aucun aperçu
    depose = liste.locator("li", has_text=nom.split(".")[0])
    depose.get_by_role("button", name=re.compile("^Monter")).click()
    page.locator("#message-papiers", has_text="Ordre changé").wait_for()
    depose = liste.locator("li", has_text=nom.split(".")[0])
    depose.get_by_role("button", name="Retirer").click()
    page.locator("#message-papiers", has_text="mis de côté").wait_for()
    cote = page.get_by_role("list", name="Papiers mis de côté")
    ligne = cote.locator("li", has_text=nom.split(".")[0])
    ligne.get_by_role("button", name=re.compile("Effacer définitivement")).click()
    assert ligne.get_by_text("Effacer pour de bon ?").count() == 1   # jamais en un seul geste
    ligne.get_by_role("button", name="Oui, effacer").click()
    page.locator("#message-papiers", has_text="effacé").wait_for()
    assert nom.split(".")[0] not in page.locator("main").inner_text()


def test_glisser_deposer_un_papier(page):
    """2.1.1 : un fichier lâché sur la zone est déposé ; un fichier d'un autre type est écarté."""
    import base64
    from tests.conftest import PNG
    ouvrir_livre(page, "Papiers")
    nom = "glisse-iphone.png" if page.mobile else "glisse-pc.png"
    zone = page.get_by_role("group", name="Déposer des papiers")
    donnees = page.evaluate_handle("""([b64, nom]) => {
        const octets = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
        const dt = new DataTransfer()
        dt.items.add(new File([octets], nom, { type: 'image/png' }))
        dt.items.add(new File(['bonjour'], 'note.txt', { type: 'text/plain' }))
        return dt
    }""", [base64.b64encode(PNG).decode(), nom])
    zone.dispatch_event("dragover", {"dataTransfer": donnees})
    assert "Lâche ici" in zone.inner_text()
    zone.dispatch_event("drop", {"dataTransfer": donnees})
    page.locator("#message-papiers", has_text="1 fichier(s) déposé(s)").wait_for()
    assert page.get_by_text("1 fichier(s) écarté(s)").count() == 1
    liste = page.get_by_role("list", name="Papiers", exact=True)
    assert nom.split(".")[0] in liste.inner_text() and "note" not in liste.inner_text()
    liste.locator("li", has_text=nom.split(".")[0]).get_by_role("button", name="Retirer").click()   # on range derrière soi
    page.locator("#message-papiers", has_text="mis de côté").wait_for()


def test_corriger_un_numero(page):
    ouvrir_livre(page, "Contacts")
    mairie = page.get_by_role("list", name="Commune et santé").locator("> li", has_text="Mairie")
    mairie.get_by_role("button", name="Modifier").click()
    numero = "05 55 00 00 4" + ("2" if page.mobile else "1")
    mairie.get_by_label("Numéro").fill(numero)
    mairie.get_by_role("button", name="Enregistrer").click()
    page.get_by_role("status").filter(has_text="Numéro enregistré").wait_for()
    assert numero in page.get_by_role("list", name="Commune et santé").locator("> li", has_text="Mairie").inner_text()


def test_un_guide_sans_adresse_officielle_n_entre_pas(page):
    aller(page, "Kit")
    page.get_by_role("button", name="Ajouter un guide").click()
    enregistrer = page.locator("#guides form").get_by_role("button", name="Enregistrer")
    assert enregistrer.is_disabled()                                # pas de fichier : pas de bouton
    assert page.locator("#guides form input[required]").count() == 3   # titre, éditeur, adresse (le fichier : bouton éteint sans lui)
    assert page.locator("#guides form").get_by_role("group", name="Fichier du guide").count() == 1


def test_un_lien_de_a_traiter_ouvre_le_bon_texte(page):
    tuile(page, "À compléter").click()
    page.get_by_role("region", name="À compléter").get_by_role("link").first.click()
    page.locator("textarea").wait_for()
    assert "À COMPLÉTER" in page.locator("textarea").input_value()


def test_reglages_refuse_un_dossier_dangereux(page):
    aller(page, "Réglages")
    dossier = page.get_by_label(re.compile("Dossier des livres"))
    bon = dossier.input_value()
    dossier.fill("/mnt")
    page.get_by_role("button", name="Enregistrer").click()
    page.locator("#message", has_text="au moins deux niveaux").wait_for()
    page.reload()
    assert page.get_by_label(re.compile("Dossier des livres")).input_value() == bon


def test_verifier_puis_livrer_depuis_connexion(page):
    """Dernier test du module : il change l'état (le kit est livré)."""
    aller(page, "Connexion")
    tuile(page, "Liseuse").click()
    page.get_by_role("button", name="Vérifier").click()
    page.locator("#rapport").wait_for()
    page.get_by_role("button", name="Livrer").click()
    page.locator("#message", has_text="Livraison faite").wait_for(timeout=20000)
    page.get_by_role("button", name="Vérifier").click()
    page.locator("#rapport", has_text="la liseuse a bien le kit").wait_for()
    aller(page, "À traiter")
    assert tuile(page, "Liseuse pas à jour").count() == 0
    assert "à jour sur la liseuse" in page.locator("#phrase").inner_text()
