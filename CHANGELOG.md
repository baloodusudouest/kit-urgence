# Changelog — kit-urgence

## 2.0.0 — 2026-11-11
Première des deux images de la 2.0 : **l'interface en lecture, la sécurité, les contrôles**. Rien n'écrit
encore dans les sources du kit (ce sera la 2.1.0). Dossier : `docs/dossier.md` ; avis du conseil : `docs/2.0-conseil.md`.

À faire avant de déployer :
- `KIT_PASSWORD` est obligatoire (le mot de passe commun) : sans lui, le conteneur refuse de démarrer ;
- `KIT_API_TOKEN` doit avoir une valeur : un jeton vide ne laisse plus `/generer`, `/synchroniser`
  et `/papier/imprime` ouverts à tout le réseau, ils sont refusés ;
- l'image n'est plus publiée sous `latest` : la stack choisit `KIT_VERSION`, Watchtower est coupé pour ce service.

Nouveau :
- **Interface** au format commun (rouge brique) : À traiter, Kit, Connexion, Réglages. PC et iPhone.
- **À traiter** : phrase d'état, puis une tuile par chose à faire (erreur, livre à retirer, kit à refabriquer,
  liseuse pas à jour, papier à réimprimer avec la liste de ce qui a changé, essai du kit, passages à compléter,
  numéros à vérifier, guides incomplets, liseuse ou contacts sans nouvelles).
- **Contrôle après fabrication** : chaque livre est rouvert avant de remplacer l'ancien ; le livre des papiers
  doit exiger un mot de passe et s'ouvrir avec celui de la stack. Un livre raté ne remplace jamais le dernier bon.
- **Le kit ne retire plus jamais seul un livre** (il serait effacé de la liseuse) : il le garde, le signale,
  et attend un oui donné à l'écran. Cas couverts : mot de passe des papiers absent, dernier papier retiré, guide renommé.
- **Essai du kit** : tous les six mois, quatre points à cocher liseuse en main ; redemandé si le mot de passe
  des papiers change. La date du dernier essai est dans la phrase d'état.
- **Mode lecture seule** (`KIT_LECTURE_SEULE=1`) : le kit fabrique ses livres mais n'écrit pas sur la liseuse.
  Refusé deux fois : à l'adresse appelée et dans la fonction qui ouvre la session.
- « Vérifier » la liseuse : relit les empreintes là-bas et compare, sans rien écrire.
- Téléchargement des livres fabriqués depuis l'écran (celui des papiers sort chiffré ; les scans déposés ne sortent jamais).
- `/status` : mêmes clés qu'avant, plus `a_traiter`, `version`, `controle`, `disparitions`, `kindle_vu_le`.
  Aucun nom de papier n'y figure.
- Journal des gestes (écran et jeton), sans nom de papier ni de contact.
- Premiers tests : 25 pour le générateur et l'API (jeu inventé, fausse liseuse), 13 d'écran.

Corrigé :
- Une fabrication du livre des papiers sur soixante-quatre échouait : le mot de passe propriétaire tiré au
  hasard pouvait commencer par un tiret, que qpdf prenait pour une option. Trouvé par les tests.
- `/cle-publique` demande maintenant le jeton (la clé se lit aussi dans l'écran Connexion).

## 1.0.1 — 2026-11-01
- Une génération réussie (démarrage, `POST /generer`, avant une livraison) remet `derniere_erreur` à `null` :
  le capteur Home Assistant « Kit urgence dernière erreur » ne garde plus une erreur déjà corrigée
  quand le Kindle est hors ligne. `/status`, ses champs et la livraison Kindle sont inchangés.
- Contacts : lecture tolérante des exports iCloud (données Siri sur plusieurs lignes ignorées,
  une carte illisible n'arrête plus la génération).

## 1.0.0 — 2026-10-29
- Première version : génération du kit (EPUB 00/01/02, guides 04, PDF chiffré 05, version papier),
  livraison et vérification sur Kindle/KOReader, API pour Home Assistant.
