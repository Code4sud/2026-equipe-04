# Équipe 04 — Hackathon Azuréen #3

Projet réalisé à Nice les 18, 19 et 20 novembre 2026, sur le thème **« L'orientation et l'employabilité grâce à l'IA »**, organisé par [Code4Sud](https://code4sud.fr).

## Le projet

**Le détecteur du potentiel caché** (sujet 4). Certains jeunes en décrochage répondent « rien » quand on leur demande ce qu'ils savent faire, alors qu'ils ont gardé leurs petits frères, réparé des scooters ou tenu la caisse d'une association. Un compagnon IA les fait raconter, révèle les compétences cachées dans leur récit en montrant d'où vient chacune, et leur laisse le dernier mot. Une psychologue du travail et de l'orientation assure le suivi dans un backoffice.

## Lancer le projet

```bash
# Prérequis : Docker Desktop démarré
./run.sh # trust
```

L'application s'ouvre sur http://localhost:8080. Le script affiche les comptes de démonstration, générés dans `.env`.

## Architecture

| Service | Rôle | Adresse sur la machine |
| --- | --- | --- |
| `frontend` | PWA React + TypeScript, servie par nginx | http://localhost:8080 |
| `backend` | API Flask, migrations et données de démo au démarrage | http://localhost:5001/api |
| `postgres` | Comptes, métadonnées des conversations, compétences | `localhost:5432` |
| `seaweedfs` | Texte des conversations, via son API S3 (bucket `conversations`) | http://localhost:8333 |
| `ollama` | Modèle `mistral`, téléchargé au premier démarrage | http://localhost:11435 |

Sur Mac, `./run.sh` utilise l'Ollama installé sur la machine s'il tourne, car Docker n'accède pas à la puce graphique. Sans lui, prévoyez au moins 8 Go de mémoire pour Docker, et des réponses nettement plus lentes.

État des services : http://localhost:8080/api/health/services

## Développer

Après un premier `./run.sh`, on peut relancer seulement la partie sur laquelle on travaille.

```bash
docker compose stop frontend backend
```

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/flask db upgrade && .venv/bin/flask --debug run --port 5001
```

```bash
cd frontend && npm ci && npm run dev
```

Le frontend de développement tourne sur http://localhost:5173 et transmet `/api` au port 5001.

| Pour changer | Fichier |
| --- | --- |
| Comportement du compagnon | `backend/prompts/compagnon.md` |
| Message d'accueil | `backend/prompts/accueil.md` |
| Relances, rythme et formules de révélation | `backend/prompts/conversation.json` |
| Compétence révélée pendant la discussion | `backend/prompts/revelation.md` |
| Repérage des compétences à valider | `backend/prompts/extraction.md` |
| Détresse, sujets sensibles et réponses relues | `backend/prompts/garde_fous.json` |
| Couleurs, typographie, espacements | `frontend/src/styles/tokens.css` |
| Textes de l'interface | `frontend/src/content/fr.ts` |

Les fichiers de `backend/prompts/` sont relus à chaque changement, sans redémarrage.

```bash
cd backend && .venv/bin/python -m pytest
```

Pour créer un compte psychologue : `docker compose exec backend flask create-user`.

## Données et garde-fous

- Le jeune décide : une compétence reste « à valider » tant qu'il ne l'a pas acceptée, et la psychologue ne voit que les compétences validées.
- Les discussions ne sont lisibles par la psychologue que si le jeune l'accepte, à l'inscription ou plus tard. Il voit ce choix dans la discussion et peut le retirer à tout moment.
- Chaque compétence cite un extrait réel des messages du jeune : le code vérifie la citation et écarte celles qu'il ne retrouve pas.
- Aucune déduction sur la santé, l'origine, la famille ou la religion. Un récit peut évoquer un proche, mais le nom et la description de la compétence n'en parlent pas.
- Un message de détresse affiche des contacts d'aide et reçoit une réponse relue, jamais générée par le modèle.

Limites actuelles : tous les comptes psychologues voient tous les jeunes, et il n'y a pas encore de suppression de compte ni de limitation des tentatives de connexion. À traiter avant d'utiliser de vraies données.

## Publier sur le site du hackathon

1. Complétez `projet.json` (nom, pitch, description, écoles, technologies, liens).
2. Ajoutez vos captures dans `captures/` et listez-les dans `projet.json`.
3. Poussez sur `main` : votre fiche apparaît sur https://orientation.code4sud.fr/projets/equipe-04 en moins d'une minute.

Toute la doc : https://orientation.code4sud.fr/doc/

## Démo en ligne

Si votre projet est un site sans serveur, il est publié automatiquement sur GitHub Pages à chaque push :
`https://code4sud.github.io/2026-equipe-04/`. Reportez cette adresse dans le champ `demo` de `projet.json`.

## Licence

MIT — voir `LICENSE`.
