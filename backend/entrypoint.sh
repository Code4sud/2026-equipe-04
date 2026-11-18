#!/bin/sh
set -e

flask db upgrade

# Le stockage peut mettre quelques secondes à accepter les écritures après son démarrage.
if [ "${SEED_DEMO:-false}" = "true" ]; then
  attempt=1
  until flask seed-demo; do
    if [ "$attempt" -ge 20 ]; then
      echo "Données de démonstration non créées : démarrage de l'API sans elles." >&2
      break
    fi
    attempt=$((attempt + 1))
    sleep 3
  done
fi

exec "$@"
