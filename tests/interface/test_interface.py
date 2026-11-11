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
    page.locator("li li button").first.click()                       # le premier texte du livre
    page.locator("pre").wait_for()
    assert len(page.locator("pre").inner_text()) > 100


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
