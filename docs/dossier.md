# Dossier du kit d'urgence 2.0 — une interface pour être autonome

Écrit le 11/11/2026 à partir du grill (deux tours). Le kit 1.0.1 est un générateur sans écran : il se pilote en déposant des fichiers dans un dossier du NAS, en éditant du YAML, et par deux boutons dans Home Assistant. Le but de la 2.0 : **ne plus avoir besoin ni de l'explorateur de fichiers, ni d'un éditeur de texte, ni de moi** pour tenir le kit à jour.

## 1. Besoin

Quatre gestes, choisis au grill :

1. **Voir ce qui manque** — ce qui empêche le kit d'être bon aujourd'hui, sans lire un journal.
2. **Déposer des fichiers** — les papiers (livre 05) et les guides officiels (livre 04).
3. **Écrire les procédures** — les textes des livres 00 et 01, dans l'appli.
4. **Régler et lancer** — adresse de la liseuse, nom du foyer ; Générer, Livrer, « Papier imprimé ».

Hors périmètre, décidé au grill :
- **Pas d'aperçu ni de téléchargement des papiers** : l'appli montre la liste des noms, rien d'autre. Le seul fichier qui sort est le livre 05, chiffré.
- **Les contacts restent dans carnet** : le kit les montre en lecture, avec un lien vers la fiche. On ne modifie pas un contact depuis le kit.
- **Home Assistant ne change pas** : mêmes adresses, même jeton, mêmes capteurs.
- **Une seule livraison.**

Ce qui rend ce kit particulier : il sert le jour où plus rien ne marche. L'appli, elle, sert les jours ordinaires, et son seul travail est que le Kindle et la version papier soient justes ce jour-là. Une erreur ici ne se voit pas : elle se découvre pendant la panne.

## 2. Technique

- **Existant gardé tel quel** : `generate.py`, `papiers.py`, `contacts.py`, `sync.py`, `status.py`. FastAPI, pandoc (EPUB), qpdf (chiffrement AES-256), WeasyPrint (PDF papier), paramiko (livraison SSH vers KOReader).
- **Ajouté** : une interface Svelte 5 / Vite 6 / Tailwind 4 reprise du socle 0.2.0, servie par le même conteneur (étape Node en plus dans le Dockerfile) ; des adresses `/api/…` pour l'interface.
- **Deux portes, deux clés** :
  - l'interface et `/api/…` : **mot de passe commun** (`KIT_PASSWORD=${CARNET_PASSWORD}`), obligatoire — sans lui le conteneur refuse de démarrer ; session par cookie ;
  - `/generer`, `/synchroniser`, `/papier/imprime` : **jeton** de Home Assistant et de carnet, inchangé.
- **Trou fermé au passage** : aujourd'hui, si `API_TOKEN` est vide, ces trois adresses répondent à tout le monde. En 2.0 elles refusent quand le jeton est vide.
- **Restent ouvertes sans clé** : `/health` et `/status` (lu par les capteurs de Home Assistant, qui n'envoient pas de jeton). `/status` contient les noms des livres et les avertissements, pas le contenu. `/cle-publique` passe derrière le mot de passe (elle est affichée dans l'écran Connexion).
- **Mode lecture seule** : `KIT_LECTURE_SEULE=1`. Refus à deux endroits : à l'adresse appelée, et dans la fonction qui écrit le fichier ou ouvre la session SSH.
- **Image** : étiquette par version (`ghcr.io/…/kit-urgence:2.0.0`) en plus de `latest` ; Watchtower coupé pour ce service, comme les autres applis qui écrivent. `KIT_VERSION` dans la stack.
- **Rien de personnel dans le dépôt public** : exemples inventés, adresses et noms dans Portainer.

## 3. Parcours des clics et des écrans

Quatre entrées. Rail à gauche sur PC, pilule d'icônes sur iPhone.

### À traiter (écran d'ouverture)
En tête, une phrase d'état : « Le kit est à jour sur la liseuse » ou ce qui ne l'est pas. Puis des tuiles, chacune avec son nombre ; une tuile à zéro s'efface.

| Tuile | Ce qu'elle compte | Ce qu'on y fait |
|---|---|---|
| **À compléter** | les passages « À COMPLÉTER » dans les procédures et les numéros publics | ouvre le texte ou le numéro à l'endroit voulu |
| **Numéros à vérifier** | les numéros publics notés « à vérifier » | corriger le numéro, ou cocher « vérifié le … » |
| **Guides manquants** | guides déclarés sans fichier, ou sans éditeur / adresse officielle | déposer le fichier, compléter la fiche |
| **Liseuse en retard** | 1 si la version du NAS n'est pas celle de la liseuse | Livrer (si elle répond), sinon la marche à suivre |
| **Papier à réimprimer** | 1 si le PDF papier a changé depuis la dernière impression confirmée | télécharger le PDF, puis « Papier imprimé » |
| **Erreur** | la dernière erreur de génération ou de livraison | le message, et Régénérer |

### Kit
Les six livres, dans l'ordre de la liseuse. Pour chacun : date de construction, poids, ce qui le compose, et **Télécharger** (le livre fabriqué, donc chiffré pour le 05).
- **00 et 01 — Procédures** : la liste des textes. Un texte s'ouvre dans un éditeur Markdown simple (zone de texte, aperçu à côté sur PC). **Enregistrer** garde l'ancienne version (les dix dernières) et régénère. « Revenir à cette version » sur chaque ancienne. Créer, renommer, supprimer un texte (supprimer = garder dans les versions).
- **02 — Contacts** : la liste telle qu'elle est dans le livre (nom, numéros), en lecture, chaque ligne avec « Ouvrir dans carnet ». En dessous, les numéros publics, modifiables ici (ils n'existent nulle part ailleurs).
- **04 — Guides** : dépôt d'un fichier (PDF ou EPUB) avec titre, éditeur et adresse officielle obligatoires ; date et langue en option. Retirer un guide.
- **05 — Papiers** : dépôt (PDF, JPG, PNG), liste des noms dans l'ordre du livre, monter / descendre, renommer, retirer. Pas d'aperçu, pas de téléchargement du fichier déposé.
- **Version papier** : télécharger le PDF, « Papier imprimé ».
- En tête d'écran : **Générer** et **Livrer**.

### Connexion
Une tuile par service, avec voyant.
- **Liseuse** : joignable ou non, version dessus, date de la dernière livraison, clé publique à copier, marche à suivre côté KOReader. Gestes : Vérifier (compare les empreintes, n'écrit rien), Livrer.
- **carnet** : date et nombre de contacts du dernier envoi reçu ; lien vers carnet. Le kit ne lit pas carnet : c'est carnet qui dépose le fichier. Geste : Vérifier (le fichier est-il là, lisible, de quand).
- **Home Assistant** : le jeton est-il réglé, date du dernier appel reçu, rappel des trois adresses.

### Réglages
Nom du foyer, adresse / port / dossier de la liseuse, intervalle de scrutation ; journal des écritures (qui a changé quoi, quand) ; version ; déconnexion.

## 4. Design

Format commun (`socle/docs/format.md`) : neutres chauds, sombre par défaut, Inter, un seul bouton plein par bloc. **Couleur : rouge brique** (sombre `#c8553d`, clair `#9c3a26`). Le rouge est la couleur de l'appli, donc il ne peut pas aussi vouloir dire « erreur » : les erreurs et les manques se disent par un pictogramme et un mot, pas par la couleur. Signature : le numéro du livre (00, 01, 02, 04, 05) en grand chiffre fin, comme sur la tranche d'un classeur.

## 5. Schéma de données

Rien ne change dans ce qui existe ; pas de base de données.

```
/data/config/config.yaml             réglages (écrit par Réglages)
/data/config/guides.yaml             fiches des guides (écrit par Kit › Guides)
/data/config/numeros-publics.yaml    numéros publics (écrit par Kit › Contacts)
/data/config/contacts-urgence.vcf    écrit par carnet, lu seulement
/data/procedures/*.md                textes (écrit par l'éditeur)
/data/procedures/.versions/<nom>/<date>.md   dix dernières versions par texte   ← nouveau
/data/guides/*   /data/papiers/*     fichiers déposés
/data/output/…                       livres fabriqués
/state/status.json                   état (lu par Home Assistant)
/state/journal.jsonl                 journal des écritures                       ← nouveau
```

Les YAML sont réécrits par l'appli : **les commentaires qu'ils contiennent aujourd'hui seront perdus** à la première modification depuis l'écran (sauf à embarquer une bibliothèque qui les garde).

Limites de dépôt : 50 Mo par fichier, extensions fermées (PDF, JPG, PNG pour les papiers ; PDF, EPUB pour les guides), nom nettoyé, jamais d'écriture hors du dossier prévu.

## 6. Plan d'implémentation

Une livraison, dans cet ordre :
1. Tests sur l'existant d'abord (il n'y en a aucun aujourd'hui) : un test fige ce que la génération produit à partir d'un jeu inventé.
2. Mot de passe, session, lecture seule, fermeture du jeton vide.
3. Adresses `/api/…` : état et tuiles, procédures et versions, numéros publics, guides, papiers, réglages, téléchargements, journal.
4. Interface : quatre écrans.
5. Tests d'écran (PC et iPhone) contre un faux dossier et une fausse liseuse.
6. Dockerfile (étape Node), workflow (étiquette par version, tests avant l'image), `homelab.yml`, `REPRISE.md`, `CHANGELOG.md`.

## Décisions prises après le conseil (11/11/2026)

Avis complet : `2.0-conseil.md`. Ce qui change par rapport au texte ci-dessus :

- **Deux images** au lieu d'une : 2.0.0 (lecture, sécurité, contrôles), puis 2.1.0 (écritures).
- **Contrôle après fabrication** : chaque livre est rouvert ; celui des papiers est déchiffré avec le mot de passe de la stack.
- **Essai du kit** tous les six mois, quatre points à cocher ; sa date est dans la phrase d'état.
- **Le kit ne retire jamais seul un livre** de la liseuse : il attend un oui à l'écran.
- **Fraîcheur** : « contacts reçus le… », « liseuse vue le… », et une tuile au-delà de six et deux mois.
- **Papier retiré** : mis de côté dans `/data/retires/` (hors de `papiers/`), visible à l'écran avec « Remettre » et « Effacer définitivement ».
- **Versions** pour tout ce que l'appli réécrit, dans `/data/versions/` (et non sous `procedures/`, que le générateur surveille).
- **Enregistrer ne fabrique pas** : le kit passe « à refabriquer » ; la fabrication se fait au bouton ou quand la liseuse se présente.
- **Réimpression** : pas de « correction mineure » ; la tuile liste ce qui a changé depuis l'impression.
- **Mots d'écran** : livres nommés par leur contenu, « Fabriquer » et « Livrer » expliqués, « Liseuse pas à jour ».
- `/cle-publique` demande le jeton ; `latest` n'est plus publiée.

## Questions ouvertes pour le conseil

1. **Supprimer un papier** : effacement réel, ou mise de côté dans un dossier `.retires/` vidé à la main ? Un scan d'identité qu'on croit retiré et qui reste sur le NAS, ou un scan retiré par erreur : lequel des deux risques pèse le plus ?
2. **`/status` ouvert sans clé** : acceptable sur le réseau local, ou faut-il un jeton en lecture (ce qui demande de modifier Home Assistant, exclu du périmètre) ?
3. **Régénérer à chaque enregistrement** d'un texte : la version papier passe « à réimprimer » à la moindre virgule. Faut-il distinguer une correction mineure ?
4. **Le mot de passe du livre 05** reste une variable de la stack : l'appli ne le montre pas et ne le change pas. Est-ce une limite à l'autonomie visée, ou la bonne frontière ?
5. **Rien ne vérifie que le kit marche vraiment** : l'appli compare des empreintes, mais personne n'ouvre le livre sur la liseuse ni n'essaie le mot de passe du 05. Faut-il un rappel d'essai périodique dans À traiter ?
