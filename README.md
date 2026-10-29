# kit-urgence

Générateur d'un **kit d'urgence numérique** pour liseuse : il prépare sur un NAS les livres à lire pendant une coupure de courant, les livre à un Kindle jailbreaké (KOReader) quand celui-ci se présente sur le réseau, puis vérifie ce que la liseuse a réellement reçu.

| Livre | Format | Source (dans le dossier de données) |
| --- | --- | --- |
| 00 – Lisez-moi d'abord | EPUB + papier | `procedures/00-*.md` |
| 01 – Procédures maison | EPUB + papier | les autres `procedures/*.md`, dans l'ordre des noms |
| 02 – Contacts | EPUB + papier | `config/contacts-urgence.vcf` + `config/numeros-publics.yaml` |
| 04a, 04b… – Guides officiels | copie exacte | fichiers de `guides/` déclarés dans `config/guides.yaml` |
| 05 – Papiers (chiffré) | PDF AES-256 | scans PDF/JPG/PNG de `papiers/` (préfixer 01-, 02-… pour l'ordre) |
| Version papier | PDF A4 | 00 + 01 + 02, dans `output/papier/` |

## Fonctionnement

1. Au démarrage, le conteneur génère le kit dans `output/Urgence/`. Un livre n'est reconstruit que si ses sources ont changé.
2. Toutes les 60 s, il vérifie si le serveur SSH de KOReader répond (`kindle.host` et `kindle.port` dans `config/config.yaml`).
3. Quand le Kindle apparaît, il régénère si besoin, envoie uniquement les livres différents, supprime les obsolètes, puis **relit les empreintes SHA-256 sur le Kindle**. `a_jour` ne passe à vrai que si tout correspond. Un livre abîmé est renvoyé ; la clé d'hôte du Kindle est épinglée à la première connexion.
4. Home Assistant lit `GET /status` et affiche les notifications du paquet `homeassistant/kit_urgence.yaml`.

Le conteneur adopte automatiquement le propriétaire du dossier de données : aucun UID/GID à configurer. Le mot de passe du livre 05 n'est jamais écrit sur disque.

## Installation

### 1. Image
Le workflow `.github/workflows/docker.yml` publie `ghcr.io/<propriétaire>/kit-urgence:latest` à chaque push sur `main` (linux/amd64).

### 2. Dossiers sur le NAS
- Un dossier de données, par exemple `/volume1/homes/<utilisateur>/kit-urgence`, rempli automatiquement au premier démarrage avec des modèles (jamais écrasés ensuite).
- Un dossier d'état hors de tout partage réseau, par exemple `/volume1/docker/kit-urgence/state`.

### 3. Service Docker
Ajouter le service de `docker-compose.yml` à la stack et renseigner les variables de `.env.example` :
`KIT_DATA_DIR`, `KIT_STATE_DIR`, `KIT_PAPIERS_PASSWORD`, `KIT_API_TOKEN`.

### 4. Autoriser le conteneur sur le Kindle
Ouvrir `http://<IP_DU_NAS>:8095/cle-publique`, puis ajouter la ligne affichée dans `koreader/settings/SSH/authorized_keys` (Kindle branché en USB, KOReader fermé).

### 5. Remplir les sources
- `config/config.yaml` : IP fixe du Kindle, nom du foyer.
- `procedures/` : compléter les passages `[À COMPLÉTER]`.
- `config/contacts-urgence.vcf` : export du groupe de contacts « Urgence ».
- `config/numeros-publics.yaml` : vérifier les numéros marqués « à vérifier ».
- `guides/` : déposer les guides déclarés dans `config/guides.yaml`.
- `papiers/` : déposer les scans.

### 6. Home Assistant
- Copier `homeassistant/kit_urgence.yaml` dans `/config/packages/`.
- Dans `configuration.yaml` : `homeassistant:` → `packages: !include_dir_named packages`.
- Ajouter dans `secrets.yaml` les clés listées en tête du paquet (URL de l'API, jeton, entité de vigilance Météo-France).
- Redémarrer Home Assistant.

## Rituel de synchronisation
Rappel le 1er du mois et en vigilance orange ou rouge : Kindle chargé → mode avion désactivé → KOReader → Réseau → Serveur SSH → Démarrer. Attendre la notification « Kit d'urgence à jour », puis couper le SSH et remettre le mode avion.

## API
| Méthode | Chemin | Rôle |
| --- | --- | --- |
| GET | `/status` | état complet (capteurs Home Assistant) |
| GET | `/cle-publique` | clé SSH du conteneur |
| POST | `/generer` | régénération complète (jeton requis) |
| POST | `/synchroniser` | livraison immédiate si le Kindle répond (jeton requis) |
| POST | `/papier/imprime` | confirme l'impression de la version papier (jeton requis) |

## Plan B (SSH hors service)
Copier le contenu de `output/Urgence/` dans `documents/Urgence/` du Kindle par USB. Les PDF s'ouvrent aussi sans KOReader ; les EPUB nécessitent KOReader.
