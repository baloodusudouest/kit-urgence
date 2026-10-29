#!/bin/sh
# Démarre en root, adopte le propriétaire du dossier /data (compte utilisateur du NAS),
# puis lance l'application avec ses droits. Aucun UID/GID à configurer.
set -eu

DATA="${KIT_DATA:-/data}"
STATE="${KIT_STATE:-/state}"
mkdir -p "$DATA" "$STATE"

# Fichiers de départ : copiés uniquement s'ils n'existent pas (jamais d'écrasement)
cd /app/seed
find . -type d -exec mkdir -p "$DATA/{}" \;
find . -type f | while read -r f; do
  [ -e "$DATA/$f" ] || cp "$f" "$DATA/$f"
done

PUID="$(stat -c %u "$DATA")"
PGID="$(stat -c %g "$DATA")"
echo "kit-urgence : exécution avec UID=$PUID GID=$PGID (propriétaire de $DATA)"

chown -R "$PUID:$PGID" "$DATA" "$STATE"
chmod 700 "$STATE"

export HOME="$STATE"
exec gosu "$PUID:$PGID" uvicorn app.main:app --host 0.0.0.0 --port 8095 --proxy-headers
