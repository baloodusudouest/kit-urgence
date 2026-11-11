# Reprise — kit-urgence

À lire avant de toucher au dépôt. Dossier : `docs/dossier.md`. Avis du conseil : `docs/2.0-conseil.md`.
Format commun des applis : dépôt `socle`, `docs/format.md`.

## Où on en est

- **2.0.0** (11/11/2026) : interface en lecture, sécurité, contrôles. Publiée, **pas encore vue sur le NAS**.
- **2.1.0** : les écritures (éditeur des procédures avec versions, numéros publics, dépôt des guides et des
  papiers avec mise de côté, réglages). À faire.

## Ce qu'il ne faut pas casser

1. **Home Assistant** lit `/status` sans clé et appelle `/generer`, `/synchroniser`, `/papier/imprime` avec le
   jeton. Les clés de `/status` de la 1.0 restent (test `test_home_assistant_garde_ses_adresses`).
2. **carnet** dépose `config/contacts-urgence.vcf` dans le dossier du kit puis appelle `/generer` avec le jeton.
3. **Un livre raté ne remplace jamais le dernier bon** (`app/controle.py`, appelé dans `generate.generer`).
4. **Le kit ne retire jamais seul un livre** : `disparitions` dans l'état, oui donné par `/api/disparitions`.
5. **Aucun nom de papier** hors de l'écran : ni dans `/status`, ni dans le journal, ni dans les avertissements.
6. **Lecture seule refusée deux fois** : à l'adresse, et dans `sync.livrer` (`garde.exiger_ecriture`).
7. **Rien de personnel dans le dépôt** (il est public) : exemples inventés, valeurs dans Portainer.

## Pièges rencontrés

- Les chemins (`KIT_DATA`, `KIT_STATE`) sont lus à l'import : les tests posent l'environnement dans
  `tests/conftest.py` avant d'importer `app`.
- La liseuse des tests est un dossier local : `conftest.brancher_liseuse` joue les commandes SSH dans un shell.
- Chaque livre porte sa date en page de garde : comparer le texte, jamais une empreinte.
- `sha_sources` regarde tout ce qui est sous `config/`, `procedures/`, `guides/`, `papiers/` : ne rien y ranger
  d'autre (les versions et les papiers mis de côté iront ailleurs sous `/data`).
- `papiers.sources` parcourt les sous-dossiers : un papier mis de côté dans `papiers/` repartirait dans le livre.
- Un mot de passe passé à qpdf ne doit jamais pouvoir commencer par un tiret (bogue corrigé en 2.0.0).
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

Pousser sur `main` : les tests tournent, puis l'image `ghcr.io/baloodusudouest/kit-urgence:<version>` est
publiée (version lue dans `app/__init__.py`). Dans Portainer : changer `KIT_VERSION`, mettre à jour la stack.
Pas de `latest`, pas de Watchtower.
