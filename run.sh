#!/usr/bin/env bash
# Prépare la configuration puis démarre toute l'application avec Docker.
set -euo pipefail
cd "$(dirname "$0")"

die() {
  printf 'Erreur : %s\n' "$*" >&2
  exit 1
}

setting() {
  grep -E "^$1=" .env | tail -n 1 | cut -d= -f2- || true
}

fill_placeholder() {
  local file=$1 placeholder=$2 value=$3
  sed "s|$placeholder|$value|g" "$file" > "$file.tmp"
  mv "$file.tmp" "$file"
}

create_env() {
  local postgres s3 jwt psy youth
  postgres=$(openssl rand -hex 24)
  s3=$(openssl rand -hex 24)
  jwt=$(openssl rand -hex 32)
  psy=$(openssl rand -hex 8)
  youth=$(openssl rand -hex 8)

  cp .env.example .env
  fill_placeholder .env change-me-postgres "$postgres"
  fill_placeholder .env change-me-s3 "$s3"
  fill_placeholder .env change-me-jwt "$jwt"
  fill_placeholder .env change-me-psy "$psy"
  fill_placeholder .env change-me-jeune "$youth"
  echo "Configuration créée dans .env, avec des secrets générés pour cette machine."
}

# Permet de lancer ensuite le backend hors Docker, avec les services du compose.
create_backend_env() {
  cp backend/.env.example backend/.env
  fill_placeholder backend/.env change-me-postgres "$(setting POSTGRES_PASSWORD)"
  fill_placeholder backend/.env change-me-s3 "$(setting S3_SECRET_KEY)"
  fill_placeholder backend/.env change-me-jwt "$(setting JWT_SECRET_KEY)"
  if [ "$native_ollama" = false ]; then
    fill_placeholder backend/.env localhost:11434 "localhost:$(setting OLLAMA_PORT)"
  fi
}

command -v docker >/dev/null 2>&1 \
  || die "Docker est introuvable. Installez Docker Desktop : https://www.docker.com/products/docker-desktop/"
docker compose version >/dev/null 2>&1 || die "Le plugin « docker compose » est introuvable."
docker info >/dev/null 2>&1 || die "Docker est installé mais ne tourne pas. Démarrez-le puis relancez."
command -v openssl >/dev/null 2>&1 || die "openssl est introuvable."

# Sur Mac, Docker n'a pas accès à la puce graphique : un Ollama natif répond bien plus vite.
native_ollama=false
if [ "$(uname -s)" = "Darwin" ] && command -v ollama >/dev/null 2>&1 \
  && curl -fsS -m 2 http://localhost:11434/api/version >/dev/null 2>&1; then
  native_ollama=true
fi

# Seuls les fichiers de secrets sont créés avec des droits restreints.
previous_umask=$(umask)
umask 077
[ -f .env ] || create_env
[ -f backend/.env ] || create_backend_env
umask "$previous_umask"

model=$(setting OLLAMA_MODEL)
if [ "$native_ollama" = true ]; then
  echo "Ollama détecté sur ce Mac : il sera utilisé à la place du conteneur."
  for wanted in "$model" "${OLLAMA_EMBED_MODEL:-bge-m3}"; do
    ollama list | awk 'NR > 1 { print $1 }' | grep -Eq "^${wanted}(:latest)?$" || ollama pull "$wanted"
  done
  export OLLAMA_URL=http://host.docker.internal:11434
  export COMPOSE_PROFILES=
fi

# Néo : reprend les dernières animations de mascotte/neo.glb.
if [ mascotte/neo.glb -nt frontend/src/mascot/neo.glb ]; then
  if [ -d frontend/node_modules ]; then
    (cd frontend && npm run --silent mascot)
  else
    echo "mascotte/neo.glb a changé : lancez « npm ci && npm run mascot » dans frontend."
  fi
fi

docker compose up -d --build

port=$(setting FRONTEND_PORT)
printf 'Démarrage de l’application'
for _ in $(seq 1 90); do
  if curl -fsS -m 2 "http://localhost:${port}/api/health" >/dev/null 2>&1; then
    printf '\n\nApplication prête : http://localhost:%s\n\n' "$port"
    printf 'Comptes de démonstration :\n'
    printf '  Psychologue : %s / %s\n' "$(setting SEED_PSY_EMAIL)" "$(setting SEED_PSY_PASSWORD)"
    printf '  Jeune       : %s / %s\n\n' "$(setting SEED_YOUTH_EMAIL)" "$(setting SEED_YOUTH_PASSWORD)"
    if [ "${COMPOSE_PROFILES-ollama}" = "ollama" ]; then
      echo "Le modèle peut encore se télécharger (environ 7 Go) : docker compose logs -f ollama-pull"
    fi
    exit 0
  fi
  printf '.'
  sleep 2
done

printf '\n'
docker compose ps
die "L'application ne répond pas. Consultez les journaux : docker compose logs backend"
