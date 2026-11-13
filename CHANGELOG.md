# Changelog — kit-urgence

## 2.3.0 — 2026-11-13
- **Connexion commune.** Connecté à l'Anneau, on n'a plus à se connecter ici : l'appli accepte le cookie « maison_session » que l'Anneau pose, quand elle est servie par la même adresse que lui. Le cookie est signé avec le mot de passe commun : une appli qui a un autre mot de passe continue de demander le sien. Il vaut trente jours, ou jusqu'au changement du mot de passe ; « Se déconnecter » le retire du navigateur.

## 2.2.1 — 2026-11-12
- Papiers conseillés : on peut glisser un fichier directement sur une ligne (elle s'allume et dit « Lâche ici »), en plus du bouton « Déposer ».

## 2.2.0 — 2026-11-12
- **Papiers à toujours avoir sur soi** : le livre des papiers (05) propose une liste de copies à déposer, par thème (identité, santé, logement, véhicule, argent, animaux). Chaque ligne a son bouton « Déposer » : le fichier prend le nom de la ligne. Une ligne se coche seule quand un papier déposé porte son nom ; « Pas concerné » l'écarte. Rien n'est obligatoire.
- Tests : 41 du back, 29 d'écran.

## 2.1.3 — 2026-11-12
- Corrigé : le livre des papiers (05) n'apparaissait dans l'écran Kit qu'une fois fabriqué — or c'est dans ce livre que l'on dépose les papiers. Les quatre livres de base sont maintenant toujours montrés ; celui des papiers dit ce qu'il attend (un dépôt, le mot de passe dans la stack, ou une fabrication).

## 2.1.2 — 2026-11-12
- Icône de l'appli (onglet du navigateur, écran d'accueil de l'iPhone) : une trousse rouge brique.
- L'image est de nouveau publiée par la même voie que les autres applis (le NAS refusait la précédente).

## 2.1.1 — 2026-11-12
- **Glisser-déposer** : les papiers et les fichiers des guides se déposent en les glissant depuis l'explorateur
  sur la zone prévue (ou en les choisissant, comme avant). Plusieurs papiers à la fois. Un fichier d'un autre
  type est écarté et annoncé ; le serveur recontrôle toujours le contenu.
- L'image est de nouveau publiée sous `latest`, en plus de sa version : la stack du NAS suit `latest`.
  Watchtower reste coupé pour le kit : la nouvelle image n'arrive que quand la stack est redéployée.
- Tests : 39 pour le générateur et l'API, 27 d'écran.

## 2.1.0 — 2026-11-11
Seconde image de la 2.0 : **l'écran écrit dans les sources du kit**. À déployer après avoir vu la 2.0.0 marcher.
Aucune variable nouvelle.

- **Textes** (Lisez-moi et procédures) : éditeur dans l'écran. Enregistrer garde l'ancienne version (les dix
  dernières, dans `versions/` du dossier du kit) ; « Voir » et « Revenir à cette version ». Créer un texte
  (titre et place dans le livre), le supprimer (il reste dans les versions). Le Lisez-moi ne se supprime pas.
- **Numéros publics** : corriger, ajouter, supprimer ; « Vérifié aujourd'hui » date la vérification et retire
  la mention « à vérifier » du livre. Un numéro qui change redevient à vérifier.
- **Papiers** : dépôt (PDF, JPG, PNG, 50 Mo au plus, contenu contrôlé), rangés à la fin du livre ; monter,
  descendre, renommer. **Retirer met de côté** (dossier `retires/`, hors de ce que le générateur parcourt) :
  « Remettre » ou « Effacer définitivement », en deux gestes. Jamais d'aperçu ni de téléchargement.
- **Guides** : un guide n'entre qu'avec titre, éditeur et adresse officielle ; dépôt du fichier d'un guide déjà
  déclaré ; fiche modifiable ; retrait (fichier mis de côté, et le livre ne quitte la liseuse qu'après un oui).
- **Réglages** : nom du foyer, adresse, port et dossier de la liseuse, intervalle de recherche. Le dossier de la
  liseuse doit être un chemin complet d'au moins deux niveaux (la livraison y efface des fichiers).
- **Enregistrer ne fabrique rien** : le kit passe « à refabriquer » ; la fabrication se fait au bouton, ou quand
  la liseuse se présente.
- Les liens de « À traiter » ouvrent le bon livre et le bon texte.
- Garde-fous : on n'écrase jamais un fichier déposé ; un nom donné par l'écran ne sert jamais de chemin ;
  la lecture seule refuse chaque écriture deux fois ; le journal ne contient aucun nom de papier.
- Les fichiers de réglages réécrits par l'écran perdent leurs commentaires ; l'original est gardé dans `versions/`.
- Non fait : renommer un texte, aperçu du texte mis en page.
- Tests : 39 pour le générateur et l'API, 25 d'écran, lancés dans l'image.

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
