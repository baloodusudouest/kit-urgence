# Changelog — kit-urgence

## 1.0.1 — 2026-11-01
- Une génération réussie (démarrage, `POST /generer`, avant une livraison) remet `derniere_erreur` à `null` :
  le capteur Home Assistant « Kit urgence dernière erreur » ne garde plus une erreur déjà corrigée
  quand le Kindle est hors ligne. `/status`, ses champs et la livraison Kindle sont inchangés.
- Contacts : lecture tolérante des exports iCloud (données Siri sur plusieurs lignes ignorées,
  une carte illisible n'arrête plus la génération).

## 1.0.0 — 2026-10-29
- Première version : génération du kit (EPUB 00/01/02, guides 04, PDF chiffré 05, version papier),
  livraison et vérification sur Kindle/KOReader, API pour Home Assistant.
