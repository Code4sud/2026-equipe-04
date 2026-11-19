# Quiz, mini-jeux, curseurs et fiche perso

## Parcours

1. À la création du compte, le jeune accepte que ses données soient transmises au Centre des Possibles et à sa psychologue (formulaire d'inscription, hors de ce module).
2. À la première connexion, il arrive sur `/jeune/quiz` : 50 questions en chapitres. Il peut passer une question ou continuer plus tard.
3. Le quiz révèle son clan (type RIASEC dominant) et débloque les jeux de `/jeune/jeux`.
4. `/jeune/fiche` présente sa fiche d'aventurier. Il y corrige ou masque ses détails et dit « C'est moi » ou « Pas moi » sur chaque curseur.
5. La psychologue voit dans la fiche du jeune les curseurs, chaque partie, chaque réponse et sa source, ainsi que chaque modification du jeune (détail corrigé avec sa réponse d'origine, détail masqué, verdict), pour pouvoir en parler avec lui.

## Garde-fous

- Aucune question ni déduction sur la santé, le handicap, l'origine, la famille, la religion, la vie amoureuse ou les opinions. `tests/test_game_content.py` contrôle les textes.
- Le jeune garde la parole sur ce qui le concerne : il corrige ou masque ses détails et donne son verdict sur chaque curseur. Masquer ne change que sa fiche, et l'interface lui dit clairement que la psychologue voit ses réponses et ses changements.
- Côté jeune, pas de pourcentage bas, pas de libellé péjoratif, pas de QI. Les curseurs bipolaires restent neutres et les autres ne montrent que les points forts.
- Le MBTI n'est ni normé ni validé. Le nom n'apparaît pas côté jeune, et aucun résultat n'est présenté comme un test MBTI.
- Univers original : aucun nom, personnage ou visuel d'une licence existante.
- Un score de jeu n'est ni un diagnostic ni une norme : la psychologue voit toujours le niveau de preuve.

## Contenu (`backend/app/game/content/`)

| Dossier ou fichier | Rôle |
|---|---|
| `traits/*.json` | Curseurs, regroupés par famille |
| `instruments/*.json` | Quiz, questionnaires et jeux (un fichier par instrument) |
| `sources/*.json` | Références bibliographiques citées par les instruments |
| `clans.json`, `sheet.json` | Clans, attributs de la fiche, niveaux, badges |
| `skill_signals.json` | Effet d'un talent validé sur les curseurs |

### Instrument

```json
{
  "id": "mon_jeu", "version": 1, "order": 10,
  "kind": "quiz | questionnaire | performance",
  "tier": "validated | translated | adapted | custom | performance",
  "title": "…", "tagline": "…", "icon": "…", "duration_min": 5, "xp": 80,
  "requires": ["onboarding"], "replayable": true, "min_answers": 12,
  "source_ids": ["ipip_mini"], "source_note": "Montré au jeune",
  "scoring_note": "Montré à la psychologue",
  "scale": { "min": 1, "max": 5, "labels": ["…"] },
  "chapters": [{ "id": "matin", "title": "…", "intro": "…" }],
  "items": []
}
```

Types de questions :

```json
{ "id": "e1", "type": "likert", "prompt": "…", "trait": "extraversion", "keyed": "+",
  "source": { "source_id": "ipip_mini", "ref": "E1", "original": "Texte d'origine", "relation": "translated" } }

{ "id": "q7", "type": "choice", "chapter": "matin", "prompt": "…", "max_choices": 1,
  "options": [{ "id": "a", "label": "…", "emoji": "🔧", "signals": [{ "trait": "riasec_r", "value": 90, "weight": 1 }] }] }

{ "id": "q1", "type": "choice", "prompt": "Ta couleur ?", "fact": "couleur_preferee",
  "fact_label": "Couleur préférée", "allow_text": true, "options": [{ "id": "jaune", "label": "Jaune", "color": "#ffd166" }] }

{ "id": "q2", "type": "text", "prompt": "Ta passion ?", "fact": "passion", "fact_label": "Passion" }
```

`relation` vaut `verbatim`, `translated`, `adapted` ou `inspired`. Une source contient `id`, `title`, `citation`, `url`, `licence`, `validated`, `adaptation` et éventuellement `note`.

Un signal (option d'un choix, ou partie d'une question Likert) peut porter son propre `tier`, qui remplace celui de l'instrument : `{ "trait": "interest_digital", "value": 75, "weight": 0.5, "tier": "custom" }` marque un indicateur maison glissé dans une question sourcée.

### Niveaux de preuve et poids dans les curseurs

| `tier` | Libellé vu par la psychologue | Sens | Poids |
|---|---|---|---|
| `validated` | Test validé | Items d'un test publié et validé, sans changement de sens | 1 |
| `performance` | Tâche cognitive publiée | Tâche cognitive publiée, score propre à ce jeu | 1 |
| `translated` | Test validé, traduction maison non validée | Items d'un test validé, traduits par l'équipe sans étude de la traduction | 0,75 |
| `adapted` | Inspiré de travaux publiés, non validé | Questions écrites par l'équipe à partir d'une théorie ou d'un test publiés | 0,5 |
| `custom` | Indicateur maison | Indicateur créé pour le projet | 0,5 |
| `talent` | Talent validé par le jeune | Talent validé par le jeune dans la discussion | 0,25 |

Une traduction maison d'un test validé prend le niveau `translated`, et `adaptation` dit qu'elle n'est pas validée. Citer une théorie (Holland, par exemple) justifie « inspiré de », jamais « test validé ».

## Calcul

Chaque réponse produit des signaux de 0 à 100. Un curseur est leur moyenne pondérée par `poids du signal × poids du niveau` (le niveau du signal s'il en porte un, sinon celui de l'instrument). Les réponses du quiz comptent dès qu'elles sont données ; celles des autres instruments comptent quand la partie est terminée. Les jeux chronométrés envoient leurs essais à la fin, et le serveur recalcule leur score (`backend/app/game/performance.py`).

## API

Jeune (`/api/me/game`) : `GET /`, `POST /instruments/<id>/runs`, `PUT /runs/<id>/answers/<item>`, `POST /runs/<id>/pause`, `POST /runs/<id>/complete`, `GET /sheet`, `PATCH /facts/<clé>`, `PUT /traits/<id>/feedback`.

Psychologue (`/api/backoffice`) : `GET /game/catalog`, `GET /youths/<id>/game`, `GET /youths/<id>/game/runs/<run>`, `GET /youths/<id>/game/traits/<trait>`.

Les types TypeScript sont dans `frontend/src/game/types.ts`.

## Développer sans Docker

```bash
cd backend && ~/Project/2026-equipe-04/backend/.venv/bin/python scripts/dev_game.py 5101
cd frontend && VITE_DEV_API_PROXY=http://127.0.0.1:5101 npm run dev -- --port 5201
```

Comptes dans `backend/scripts/dev_game.py`.
