# Reprise — kit-urgence

À lire avant de toucher au dépôt. Dossier : `docs/dossier.md`. Avis du conseil : `docs/2.0-conseil.md`.
Format commun des applis : dépôt `socle`, `docs/format.md`.

## Où on en est

- **2.0.0** (11/11/2026) : interface en lecture, sécurité, contrôles. Publiée, **pas encore vue sur le NAS**.
- **2.1.0** (11/11/2026) : les écritures (`app/ecrits.py`). Publiée, **pas encore vue sur le NAS**.
  À déployer après la 2.0.0, une fois celle-ci vue en vrai (Home Assistant, carnet, une livraison).
- **2.1.1** (12/11/2026) : glisser-déposer (`frontend/src/lib/kit/Depot.svelte`) ; `latest` de nouveau publiée.
- Idées gardées pour plus tard : dates d'expiration des papiers, batterie de la liseuse, renommer un texte.

## Ce qu'il ne faut pas casser

1. **Home Assistant** lit `/status` sans clé et appelle `/generer`, `/synchroniser`, `/papier/imprime` avec le
   jeton. Les clés de `/status` de la 1.0 restent (test `test_home_assistant_garde_ses_adresses`).
2. **carnet** dépose `config/contacts-urgence.vcf` dans le dossier du kit puis appelle `/generer` avec le jeton.
3. **Un livre raté ne remplace jamais le dernier bon** (`app/controle.py`, appelé dans `generate.generer`).
4. **Le kit ne retire jamais seul un livre** : `disparitions` dans l'état, oui donné par `/api/disparitions`.
5. **Aucun nom de papier** hors de l'écran : ni dans `/status`, ni dans le journal, ni dans les avertissements.
6. **Lecture seule refusée deux fois** : à l'adresse, et dans `sync.livrer` (`garde.exiger_ecriture`).
7. **Les écritures** (`ecrits.py`) : jamais d'écrasement, ancien gardé dans `/data/versions/`, retiré mis de côté
   dans `/data/retires/`, un nom venu de l'écran n'est jamais un chemin.
8. **Rien de personnel dans le dépôt** (il est public) : exemples inventés, valeurs dans Portainer.

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
