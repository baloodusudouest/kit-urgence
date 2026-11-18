# Reprise — kit-urgence

À lire avant de toucher au dépôt. Dossier : `docs/dossier.md`. Avis du conseil : `docs/2.0-conseil.md`.
Format commun des applis : dépôt `socle`, `docs/format.md`.

## Où on en est

- **2.6.0** (18/11/2026, santé des tâches de fond, socle 0.9.0) : `/health` fusionne `maison.sante(...)` (`version_socle`, `taches`, `copie_base` = null : pas de base). Tâches dans `maison.TACHES` : `scrutation` (régulière, période = `max(15, scrutation_secondes)`, redéclarée à chaque tour : `main._tour_de_scrutation`), `fabrication` et `livraison` (à la demande ; `main.TACHE_*`). Le registre vit en mémoire : **un seul worker uvicorn**. Se pose par-dessus la 2.5.7, qui n'est pas encore déployée (ses remarques valent toujours). Jamais essayé sur la vraie installation.
- **2.5.7** (18/11/2026, constats moyens de l'audit) : délais de pandoc/qpdf (M43) ; `PAPIERS_PASSWORD` de 12 caractères au moins, sinon seul le livre 05 n'est pas fabriqué (`Config.papiers_probleme`) ; empreinte du mot de passe des papiers en PBKDF2 salé (`config.empreinte_papiers`, sel dans `/state/sel-papiers`), anciennes empreintes réécrites au démarrage (`generate.reprendre_empreintes_anciennes`). **Avant de déployer** : vérifier que `PAPIERS_PASSWORD` de la stack fait 12 caractères ou plus, sinon le livre des papiers ne sera plus refait et sera proposé au retrait (tuile « disparition »). Jamais essayé sur la vraie installation.
- **2.5.1** (16/11/2026) : `PUT /api/reglages` et `POST /api/restaurer` appellent `exiger_ecriture("dans les réglages du kit")` (409 en lecture seule), choix de Julien ; `Reglages.svelte` grise les champs et les boutons. Jamais essayé sur la vraie installation.
- **2.5.0** (16/11/2026) : réglages sauvegardés et restaurés ; anciens noms retirés. Module `app/maison.py` au contrat 2 (copie du socle, ne pas le modifier ici).
  - Réglages d'usage : ceux de l'écran Réglages, gardés dans `config/config.yaml` (aucun n'était dans la stack, donc aucune reprise de variable). `app/sauvegarde.py` les présente à plat (`actuels`, `corps_ecran`) et tient la liste `EXCLUS` (utilisateur SSH, papiers, clé SSH, mots de passe, contacts).
  - `GET /externe/sauvegarde` (jeton commun seul, 404 si `MAISON_JETON` vide), `GET/POST /api/restaurer` (session ; faux Anneau des tests : `main.LIRE_ANNEAU`). La restauration repasse par `ecrits.enregistrer_reglages` (mêmes contrôles ; une valeur refusée → 422, rien n'est écrit).
  - Les réglages internes se changent et se restaurent **même en lecture seule** : `garde.reglages_internes()` lève l'interdiction pendant `ecrits.enregistrer_reglages` seulement ; textes, papiers, guides, numéros et liseuse restent refusés deux fois. Mauvais type → 400 (`ecrits._entier`, `_texte_simple`), hors bornes → 422.
  - Mot de passe : `MAISON_PASSWORD` seul (12 caractères au moins) ; plus de `KIT_PASSWORD`. Lien carnet : annuaire de l'Anneau seul ; plus de `KIT_CARNET_URL`. Restent lues : `MAISON_PASSWORD`, `MAISON_JETON`, `MAISON_JETON_ANCIEN`, `MAISON_LECTURE_SEULE`, `MAISON_ANNEAU_URL` (facultative), `KIT_LECTURE_SEULE`, `PAPIERS_PASSWORD`, `API_TOKEN`, et les chemins `KIT_DATA`, `KIT_STATE`, `KIT_ASSETS`.
  - **Déploiement en deux temps** : d'abord la nouvelle image avec la stack actuelle (les réglages sont repris des anciennes variables au premier démarrage — pour le kit, il n'y en a aucune : les réglages sont déjà dans `config.yaml`), vérifier Réglages, puis la nouvelle stack sans les anciennes lignes (`KIT_PASSWORD`, `KIT_CARNET_URL`). Avant le premier temps : `MAISON_PASSWORD` doit être dans la stack du kit, sinon il ne démarre plus.
  - **Jamais essayé sur la vraie installation** (ni la sauvegarde par l'Anneau, ni la restauration).
- **2.4.0** (16/11/2026) : variables communes (module `app/maison.py`, copie du socle 0.5.0 : ne pas le modifier ici, `python tools/diffuser_maison.py ../kit-urgence` depuis le socle). `config.mot_de_passe` lit `MAISON_PASSWORD` (repli `KIT_PASSWORD`) ; `garde.lecture_seule` / `garde.origine` lisent `MAISON_LECTURE_SEULE` (`KIT_LECTURE_SEULE` l'emporte, « 1 » accepté) ; `main._auth` accepte `API_TOKEN` ou `maison.jetons()` (`jetons_acceptes`), mais refuse (503) tant qu'`API_TOKEN` est vide : **règle gardée**, Home Assistant s'en sert ; `config.ANNUAIRE` + `config.carnet_url(prive)` (tuile « carnet », repli `KIT_CARNET_URL`), `prive` posé par la garde dans `main._PRIVE`. Jamais essayé sur la vraie installation : les nouvelles variables ne sont pas encore dans la stack.
- **2.3.1** (13/11/2026) : toujours sombre (blocs `prefers-color-scheme: light` retirés, variante `dark:` partout).
- **2.3.0** (13/11/2026) : connexion commune avec l'Anneau — cookie `maison_session` (accepté ; `Sessions.connecte`, `commun_valide` dans `app/auth.py`). Jamais essayée sur la vraie installation.
- **2.0.0** (11/11/2026) : interface en lecture, sécurité, contrôles. Publiée, **pas encore vue sur le NAS**.
- **2.1.0** (11/11/2026) : les écritures (`app/ecrits.py`). Publiée, **pas encore vue sur le NAS**.
  À déployer après la 2.0.0, une fois celle-ci vue en vrai (Home Assistant, carnet, une livraison).
- **2.1.1** (12/11/2026) : glisser-déposer (`frontend/src/lib/kit/Depot.svelte`) ; `latest` de nouveau publiée.
- **2.2.0** (12/11/2026) : papiers conseillés dans le livre 05 (`ecrits.PIECES`, `ecrits.pieces`, `config/papiers-conseilles.yaml` pour les lignes écartées). Un papier répond à une ligne par les mots de son nom.
- Idées gardées pour plus tard : dates d'expiration des papiers, batterie de la liseuse, renommer un texte.

## Ce qu'il ne faut pas casser

1. **Home Assistant** lit `/status` sans clé et appelle `/generer`, `/synchroniser`, `/papier/imprime` avec le
   jeton (`API_TOKEN`, obligatoire ; `MAISON_JETON` accepté en plus depuis la 2.4.0, pour carnet).
   `/externe/sauvegarde` (2.5.0) : jeton commun seul, jamais `API_TOKEN`. Les clés de `/status` de la 1.0 restent (test `test_home_assistant_garde_ses_adresses`).
2. **carnet** dépose `config/contacts-urgence.vcf` dans le dossier du kit puis appelle `/generer` avec le jeton.
3. **Un livre raté ne remplace jamais le dernier bon** (`app/controle.py`, appelé dans `generate.generer`).
4. **Le kit ne retire jamais seul un livre** : `disparitions` dans l'état, oui donné par `/api/disparitions`.
5. **Aucun nom de papier** hors de l'écran : ni dans `/status`, ni dans le journal, ni dans les avertissements.
6. **Lecture seule refusée deux fois** : à l'adresse, et dans `sync.livrer` (`garde.exiger_ecriture`).
   Seule exception (2.5.0) : les réglages internes (`config.yaml`), par `garde.reglages_internes()`.
7. **Les écritures** (`ecrits.py`) : jamais d'écrasement, ancien gardé dans `/data/versions/`, retiré mis de côté
   dans `/data/retires/`, un nom venu de l'écran n'est jamais un chemin.
8. **Rien de personnel dans le dépôt** (il est public) : exemples inventés, valeurs dans Portainer.
9. **Rien de secret dans la sauvegarde** : `sauvegarde.EXCLUS` + `maison.est_secret` ; test `test_sauvegarde_rend_les_reglages_sans_secret`.

## Pièges rencontrés

- Les chemins (`KIT_DATA`, `KIT_STATE`) sont lus à l'import : les tests posent l'environnement dans
  `tests/conftest.py` avant d'importer `app`.
- La liseuse des tests est un dossier local : `conftest.brancher_liseuse` joue les commandes SSH dans un shell.
- Chaque livre porte sa date en page de garde : comparer le texte, jamais une empreinte.
- `sha_sources` regarde tout ce qui est sous `config/`, `procedures/`, `guides/`, `papiers/` : ne rien y ranger
  d'autre (les versions et les papiers mis de côté iront ailleurs sous `/data`).
- `papiers.sources` parcourt les sous-dossiers : un papier mis de côté dans `papiers/` repartirait dans le livre.
- Un mot de passe passé à qpdf ne doit jamais pouvoir commencer par un tiret (bogue corrigé en 2.0.0).
- **qpdf 12 refuse l'appel de chiffrement du kit** (`papiers.construire`, écrit pour qpdf 11 de Debian bookworm) :
  le livre des papiers ne sort plus. Les tests tournent donc **dans l'image**. Ne pas changer d'image de base
  sans réécrire cet appel et voir les tests verts.
- La liseuse est servie toute seule dès qu'elle apparaît : enregistrer une source, c'est publier.
- `pages/Connexion.svelte` est la page du mot de passe ; l'écran des services est `pages/Services.svelte`.

## Lancer

```
pip install -r requirements-dev.txt      # + pandoc 3.1.3, qpdf, pango
python -m pytest -q tests --ignore=tests/interface
cd frontend && npm ci && npx vite build && cd ..
pip install playwright && python -m playwright install chromium
python -m pytest -q tests/interface
```

## Déployer

Pousser sur `main` : l'image est construite, tous les tests tournent dedans, puis l'image `ghcr.io/baloodusudouest/kit-urgence:<version>` est
publiée sous `latest` et sous sa version (lue dans `app/__init__.py`). Dans Portainer : redéployer la stack
en retéléchargeant l'image. Pas de Watchtower pour ce service.
