# Changelog — kit-urgence

## 2.7.1 — 20 novembre 2026 (socle 0.11.1)
- Copies communes du socle 0.11.1 : sur une fiche « Connexion », le titre devient « Pour le relier » quand le réglage se fait dans Réglages de l'appli (et non dans la stack).
- **Jamais essayé sur la vraie installation.**

## 2.7.0 — 20 novembre 2026 (fiches « Connexion » communes, contrat 3)
- **Écran Connexion au format commun des applis maison** (module `app/maison.py` et interface `frontend/src/lib/services/` du socle 0.11.0, copiés tels quels, empreintes contrôlées par les tests) : trois fiches dépliées, **Liseuse**, **carnet** et **Home Assistant**, chacune avec son point d'état et son état en mots, **Ce qui est lu**, **Ce qui est écrit** (textes repris de l'ancien écran), l'âge du dernier essai et le bouton **Vérifier**, qui ne teste que son service et n'écrit rien.
- **Liseuse** : « Vérifier » regarde si le serveur SSH de KOReader répond, puis fait la comparaison de toujours (empreintes des livres relues sur la liseuse, rien d'écrit) et la résume sous la fiche (« N livre(s) identiques : la liseuse a bien le kit du NAS. », ou les livres différents, absents, en trop). Pendant une fabrication ou une livraison, la comparaison n'est pas lancée. **Livrer** est le geste plein de la fiche (route `POST /api/livrer` inchangée ; son résultat sert d'essai). La fiche porte un **guide** : réglages lus (adresse, dossier, recherche, vue, dernière livraison, kit dessus), **Allumer normalement**, **En cas de problème** (pas réglée, ne répond pas, lecture impossible, dossier trop large, liseuse qui s'endort, lecture seule, plan B par USB) et **Installation (une seule fois)** avec la clé du kit à copier pour `koreader/settings/SSH/authorized_keys`. Repris de l'ancien écran, d'À traiter, du README, du livre 00 et du paquet Home Assistant ; pas de commande à taper (le projet n'en a pas pour la liseuse).
- **carnet** (appli maison) : « Vérifier » lit seulement le fichier de contacts déposé par carnet (nombre, date). Relié quand `KIT_API_TOKEN` est réglé (sans lui, carnet ne peut pas demander de fabrication). Le lien « Ouvrir carnet » de l'ancienne fiche disparaît (les liens vers carnet restent dans Kit › Contacts).
- **Home Assistant** : « Vérifier » ne lui demande rien (c'est lui qui appelle le kit) et dit le dernier appel avec jeton. Relié quand `KIT_API_TOKEN` est réglé.
- La liseuse n'a pas de variable de stack : non réglée, sa fiche dit « Aucune variable : l'adresse de la liseuse se règle dans Réglages ».
- Nouvelles routes : `GET /api/maison/services` et `POST /api/maison/services/{id}/verifier`, ouvertes par la session du kit ou par **`ANNEAU_CLE`** (nouvelle variable, facultative : l'Anneau lit les fiches ; vide = porte fermée). `MAISON_JETON` et `API_TOKEN` ne les ouvrent pas.
- **À retirer à la version suivante** : `GET /api/connexions` et `POST /api/liseuse/verifier` (elles ne servaient qu'à l'ancien écran `pages/Services.svelte`, retiré).
- Tests : 79 du back (dont 7 pour les fiches : forme du contrat 3, accès, Vérifier sans écriture même en lecture seule, guide, Livrer qui sert d'essai, empreintes), 33 d'écran (Connexion sur PC et iPhone : fiches, guide, Vérifier puis Livrer).
- **Jamais essayé sur la vraie installation.**

## 2.6.1 — 18 novembre 2026 (mot de passe court : avertissement seulement)
- **Mot de passe des papiers court (moins de 12 caractères)** : choix de Julien, le livre des papiers est de nouveau **fabriqué et chiffré comme avant** ; l'écran avertit seulement (Réglages, livre 05, avertissements : « mot de passe des papiers court (N caractères) : 12 au moins conseillés »). Rien n'est proposé au retrait à cause de la longueur. Remplace le refus de la 2.5.7 (M45).
- Mot de passe absent : inchangé (livre des papiers non fabriqué, dit en clair).
- Gardés de la 2.5.7 : l'empreinte lente et salée (PBKDF2) et la reprise des anciennes empreintes au premier démarrage. Un livre des papiers déjà fait avec un mot de passe court en 2.5.6 n'est ni refait ni proposé au retrait après la mise à jour (test).

## 2.6.0 — 18 novembre 2026 (santé des tâches de fond)
- **`/health` dit l'état des tâches de fond** (module commun `maison.py`, socle 0.9.1) ; les anciens champs (`ok`, `version`) ne changent pas. Nouveaux champs : `version_socle`, `taches`, `copie_base`.
- Tâches suivies : **scrutation** (régulière, toutes les `scrutation_secondes` des Réglages, 15 s au moins ; 60 s par défaut), **fabrication** (à la demande : fabrication des livres, par Home Assistant, carnet, l'écran ou au démarrage) et **livraison** (à la demande : envoi sur la liseuse). La livraison qui suit l'apparition de la liseuse a sa propre tâche : un envoi long ne fait pas croire que la scrutation est bloquée. Une livraison refusée en lecture seule n'est pas comptée comme ratée.
- Les messages d'erreur des tâches ne sortent qu'avec le jeton commun (`MAISON_JETON`) ou une session ouverte ; `API_TOKEN` (Home Assistant) ne les ouvre pas.
- Copie des bases : aucune (le kit n'a pas de base SQLite) ; `copie_base` vaut `null`.
- Comportement inchangé : une erreur de scrutation est toujours notée au journal et la boucle continue ; une fabrication ou une livraison ratée remplit toujours `derniere_erreur`.
- Se déploie par-dessus la 2.5.7 (pas encore déployée) : les remarques de la 2.5.7 valent toujours.

## 2.5.7 — 18 novembre 2026 (constats moyens de l'audit)
- **M43** : délais maximaux sur pandoc (300 s par livre) et qpdf (300 s pour fusionner et chiffrer, 60 s pour rouvrir le livre des papiers) ; un outil qui ne finit pas est arrêté, le livre est noté en échec (« fabrication arrêtée : plus de … s ») et l'ancien reste. Le canal SSH avait déjà son délai (2.5.2).
- **M45** : `PAPIERS_PASSWORD` doit faire 12 caractères au moins ; plus court, le livre des papiers n'est pas fabriqué et l'écran le dit (Réglages, livre 05, avertissements), le reste du kit démarre et se fabrique ; comme pour un mot de passe absent, un livre des papiers déjà fait n'est retiré qu'après un oui à l'écran.
- **M45** : l'empreinte du mot de passe des papiers gardée sur disque (registre des livres, état, essai en vrai) est lente et salée (PBKDF2, 200 000 tours, sel propre à l'installation dans `/state/sel-papiers`) au lieu d'un SHA-256 simple. Au premier démarrage, les anciennes empreintes sont relues puis réécrites : le livre des papiers n'est pas refait et l'essai en vrai n'est pas redemandé.
- `maison.py` du socle 0.8.2 (audit M3) : réglages secrets reconnus par mots, adresse avec identifiant écartée, champ `ecartes` dans la sauvegarde (noms seulement).

## 2.5.6 — 18 novembre 2026 (cookies Secure)
- **Cookies `Secure` en https** (audit du 17/11/2026, même correctif dans toutes les applis maison) : ouverte en https (directement, derrière Tailscale Serve qui le dit par `X-Forwarded-Proto`, ou d'après l'origine de la page), l'appli pose ses cookies de session avec l'attribut `Secure` : ils ne partent jamais en clair. En http (adresse locale), rien ne change.
- `entrypoint.sh` refuse de lancer l'appli en root quand `/data` appartient à root (dossier créé par Docker) et dit le remède ; dépannage seulement : `MAISON_ROOT_ACCEPTE=oui`.

## 2.5.5 — 18 novembre 2026 (révocation du cookie commun)
- **« Se déconnecter » dans l'Anneau ferme vraiment la connexion commune** (audit du 17/11/2026, même correctif dans toutes les applis maison) : le cookie commun `maison_session` porte maintenant la génération tenue par l'Anneau (« génération.expiration.signature ») ; « Se déconnecter » l'augmente, et chaque appli la lit dans l'annuaire de l'Anneau (`/externe/services`, au plus une minute de retard) : un cookie commun d'avant la déconnexion ne vaut plus nulle part. Si l'Anneau ne répond pas, le cookie reste accepté comme avant (rien ne se bloque). **Toutes les applis doivent être à jour ensemble** ; une seule reconnexion est demandée après la mise à jour.
- Module commun `maison.py` (socle 0.8.0) : `generation_commune()`, `definir_generation_commune()` ; l'annuaire lit aussi `generation_commune` (une ancienne réponse de l'Anneau, liste seule, reste lue).

## 2.5.4 — 2026-11-17 (corrections de l'audit, suite)
- Réordonner les papiers : le nom d'origine reste dans le nom provisoire, et un réordonnancement coupé par un arrêt est repris au démarrage (avant, les papiers restaient cachés et sortaient du livre sans le dire).

## 2.5.3 — 17 novembre 2026 (connexion plus sûre)
- **Connexion plus sûre** (audit du 17/11/2026, même correctif dans toutes les applis maison) :
  - un cookie portant un caractère non ASCII donnait une erreur 500 sur toute l'API ; il est maintenant simplement refusé ;
  - les clés qui signent les cookies (celui de l'appli et le cookie commun `maison_session` posé par l'Anneau) sont tirées du mot de passe par PBKDF2 : un cookie capté sur le réseau local ne permet plus de chercher le mot de passe à grande vitesse. **Toutes les applis doivent être à jour ensemble** ; une seule reconnexion est demandée après la mise à jour ;
  - des essais de mot de passe lancés en parallèle ne contournent plus le délai : au-delà de 30 essais en 5 minutes, tout est refusé sans comparer.
- Module commun `maison.py` (socle 0.7.0) : l'annuaire de l'Anneau est relu 30 s après un échec (avant : 10 min sans adresses après un redémarrage de la stack) ; un réglage `nan` ou infini est refusé ; un `reglages.json` abîmé est mis de côté (`.corrompu`) au lieu d'être écrasé.

## 2.5.2 — 2026-11-17 (corrections de l'audit)
- **Livre tronqué** : si la liaison avec la liseuse tombait pendant l'envoi, le fichier partiel remplaçait le dernier bon livre. Il ne prend maintenant la place de l'ancien que s'il est arrivé entier (taille contrôlée sur la liseuse) ; sinon il est effacé et l'ancien reste.
- **Dossier trop large refusé** : `/mnt/us` ou `/mnt/us/documents` étaient acceptés comme dossier de la liseuse, et la livraison y aurait effacé tous les livres qui ne sont pas au kit. Il faut un dossier à lui (ex. `/mnt/us/documents/Urgence`) ; la livraison le revérifie avant tout effacement.
- **Liseuse endormie** : délais maximaux sur la connexion SSH et sur chaque échange (120 s sans octet) ; avant, une liseuse qui s'endormait en plein envoi figeait toute l'appli.

## 2.5.1 — 2026-11-16

- **Lecture seule stricte pour les réglages** (choix de Julien) : en lecture seule, les réglages du kit (foyer, liseuse, recherche) ne se changent plus ni ne se restaurent depuis l'Anneau, comme avant la 2.5 ; champs et boutons grisés dans Réglages. Les autres changements de la 2.5.0 restent.

## 2.5.0 — 16 novembre 2026
- **Réglages sauvegardés chez l'Anneau** (module commun `app/maison.py`, contrat 2, copié tel quel) :
  - le kit n'avait aucun réglage d'usage dans la stack ; ses réglages de l'écran Réglages (nom du foyer, adresse, port et dossier de la liseuse, intervalle de recherche) restent dans `config/config.yaml` ;
  - nouvelle adresse `GET /externe/sauvegarde` pour l'Anneau, ouverte seulement par le jeton commun `MAISON_JETON` (fermée, 404, s'il est vide ; `API_TOKEN` ne l'ouvre pas). Ne sortent jamais : papiers, clé et utilisateur SSH, mots de passe, contacts ;
  - nouvelle tuile **Restaurer les réglages** dans Réglages : choisir une date, voir les différences (avant → sauvegardé), confirmer. Anneau injoignable ou rien ce jour-là : un message clair. Une ligne au journal ;
  - les réglages du kit se changent et se restaurent **même en lecture seule** : ce sont ses réglages à lui ; la lecture seule protège toujours la liseuse et les sources des livres ;
  - une valeur du mauvais type (texte à la place d'un nombre…) est refusée avec un message (400).
- **Anciens noms retirés** : le kit ne lit plus `KIT_PASSWORD` (seul `MAISON_PASSWORD`, 12 caractères au moins, sinon le kit ne démarre pas) ni `KIT_CARNET_URL` (le lien vers carnet vient de l'Anneau seulement ; sans lui, pas de lien).
- Inchangés : `API_TOKEN` obligatoire (Home Assistant), `MAISON_JETON` accepté en plus sur les adresses à jeton (carnet), `KIT_LECTURE_SEULE` (forçage pour le kit seul), `PAPIERS_PASSWORD`.
- Tests : 56 du back (dont 7 nouveaux pour la sauvegarde et la restauration), 33 d'écran (Restaurer sur PC et iPhone).

## 2.4.0 — 2026-11-16
- **Variables communes de la maison** (module `app/maison.py` du socle 0.5.0, copié tel quel) :
  - mot de passe : `MAISON_PASSWORD`, repli sur `KIT_PASSWORD` ;
  - lecture seule : `MAISON_LECTURE_SEULE` pour toute la maison ; `KIT_LECTURE_SEULE`, si elle dit oui (« 1 » reste accepté) ou non, l'emporte pour le kit. Réglages et le bandeau disent « toute la maison » ou « cette appli » ;
  - jeton commun `MAISON_JETON` (et `MAISON_JETON_ANCIEN` pendant un changement) accepté sur `/generer`, `/synchroniser`, `/papier/imprime` et `/cle-publique`, en plus d'`API_TOKEN` : carnet pourra passer au jeton commun. `API_TOKEN` reste obligatoire tant que Home Assistant s'en sert : sans lui, ces adresses refusent, même avec `MAISON_JETON` ;
  - lien « Ouvrir dans carnet » : adresse lue dans l'Anneau (tuile « carnet » ; adresse privée quand le kit est ouvert par Tailscale), repli sur `KIT_CARNET_URL`.
- Mot de passe des papiers (`PAPIERS_PASSWORD`) inchangé.
- Rien ne change tant que la stack n'a pas les nouvelles variables : chaque ancien nom reste lu.
- Tests : 50 du back (dont 8 pour les variables communes), 31 d'écran.

## 2.3.1 — 2026-11-13
- **Toujours sombre.** Le thème clair est retiré : l'appli est sombre partout, ouverte seule comme dans l'Anneau, quel que soit le réglage du téléphone.

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
