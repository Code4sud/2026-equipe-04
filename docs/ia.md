# L'IA de Flair : discussion, lecteur de talents et garde-fou

Tout tourne en local avec Ollama. Mesures faites le 19 novembre 2026 sur le Mac de l'équipe
(puce M5 Pro, 24 Go de mémoire partagée, dont environ 8 Go pris par Docker).

## En bref

- **Un seul modèle de langage, Gemma 4 12B** (`gemma4:12b`, Google, licence Apache 2.0), fait
  trois choses : il écrit les réponses de Truffe, il lit les messages pour repérer les talents,
  et il trie les sujets interdits. `bge-m3` rapproche les récits du référentiel ROME/ESCO.
- **Pourquoi un seul modèle :** deux modèles de 8 Go ne tiennent pas ensemble à côté de
  Docker. Ollama devrait alors décharger et recharger les modèles à chaque tour (3 à 5 s), ce
  qui couperait la discussion. Un modèle plus gros (Gemma 4 26B, Qwen 3.6, Mistral Small 3.2)
  ne tient pas non plus en mémoire graphique sur cette machine.
- **Le lecteur ne gêne jamais la discussion :** il lit en arrière-plan, et s'interrompt dès
  qu'un jeune attend une réponse, puis reprend juste après (`READER_YIELDS_TO_CHAT`). Mesuré :
  Truffe répond en 2,2 s pendant une longue analyse, au lieu d'attendre la fin de celle-ci.

## Les trois rôles, dans l'ordre d'un message

1. **Garde-fou** (`app/services/moderation.py`, `prompts/moderation.md`), avant toute réponse,
   en 0,4 s environ. Un lexique de mots sans double sens (`prompts/garde_fous.json`) et le
   modèle classent le message : discussion normale, sujet interdit (sexe, actes illégaux,
   violence, haine), confidence de violences subies, ou détresse. Une alerte vue par le modèle
   seul est relue une seconde fois avant d'être suivie, pour ne jamais refuser un vrai récit
   (« le patron me laisse la caisse »).
   - Sujet interdit : « Je ne peux pas parler de ce sujet. », puis Truffe propose autre chose,
     si possible en reprenant ce que le jeune a raconté avant. Le message n'est jamais analysé
     et n'est plus montré au modèle.
   - Violences subies : Truffe ne renvoie jamais le jeune. Il le remercie, dit que ce n'est pas
     sa faute, et l'oriente vers le 119, le 116 006, le 3018 ou le 17, avec la carte d'aide.
     Le message est signalé à la psychologue dans le backoffice.
   - Détresse : réponse de crise existante (3114, 112).
2. **Truffe** (`app/services/chat.py`, `prompts/compagnon.md`, `prompts/conversation.json`).
   Le modèle écrit librement, au lieu de l'ancien gabarit « réaction + question » qui donnait
   un effet interrogatoire. Une consigne de tour varie la forme : une question ouverte, une
   simple impression, une invitation à raconter, ou une autre porte quand le sujet s'épuise.
   Environ une réponse sur deux pose une question ; les autres réagissent ou invitent à
   raconter. Un mot qui répond vraiment à sa question (« Jett », « le foot ») va au modèle ;
   un simple « ouais » reçoit une relance relue, et juste après un talent annoncé, un « ouais »
   ou un « bof » reçoit une réponse adaptée (le talent est sur sa carte, il peut le retirer).
   Chaque réponse est relue avant d'être montrée : longueur, une question au plus, français
   correct, pas de salutation, pas de « talent » ni de « compétence » (le lecteur s'en charge
   avec une citation vérifiée), rien sur la santé, les origines, la religion ou les proches,
   jamais décourageante, jamais répétée. Sinon, le modèle réécrit (trois essais au plus).
3. **Lecteur de talents** (`app/services/talent_detector.py`), en arrière-plan après chaque
   réponse : indices du référentiel, rapprochement par `bge-m3`, lecture libre par le modèle,
   puis vérification de chaque paire talent/citation. Il reçoit maintenant la réplique de
   Truffe à laquelle le jeune répond, pour comprendre « oui, tous les samedis ». Le référentiel
   passe de 52 à 71 entrées (calcul, service en salle, sécurité, électricité, leadership,
   démarches, petit business, danse, théâtre, bénévolat...).

## Comparatif des modèles

Mesures du 19 novembre 2026, Docker et l'application en marche, sur les jeux de test de
`backend/eval/` (voir « Mesurer » plus bas).

### Discussion et garde-fou

| Modèle | Mémoire | Garde-fou (66 messages) | Réponse de Truffe (médiane) | Ce qu'on a vu |
|---|---|---|---|---|
| **Gemma 4 12B** (`gemma4:12b`), retenu | 7,8 Go | 98 % | 2,1 s | Français naturel, réagit aux détails, suit les consignes |
| Qwen 3.5 9B (`qwen3.5:9b`) | 7,6 Go | 94 % | 1,7 s | Fautes (« t'organises-vous », accords au féminin), laisse passer « porno » et « onlyfans » |
| Ministral 3 14B (`ministral-3:14b`) | 9 Go | 98 % | 11,6 s | Trop lent sur ce Mac, invente un nom de jeu, un gros mot |
| Mistral Nemo 12B (`mistral-nemo`, l'ancien) | 7,5 Go | 97 % | 6,0 s | Répète « Raconte-moi la fois où » à chaque tour, prend une victime pour de la violence |
| d3 4B, pplx-decider-flash 4B, nimble 9B (modèles de « décision ») | 3,6 à 9,4 Go | 98 %, 95 %, 97 % | sans objet | Pas mieux que Gemma 4, et un deuxième modèle en mémoire ; pplx-decider classe deux victimes en « sexuel » |

Ministral 3 et Mistral Nemo tournent avec llama-server, qui rechargeait le modèle à chaque
changement de taille de contexte pendant ces mesures : leurs temps sont pessimistes, mais leurs
réponses restaient moins bonnes. Toutes les requêtes utilisent maintenant la même taille.

Le garde-fou complet (lexique, Gemma 4, relecture des alertes) classe bien 65 des 66 messages
étiquetés, et ne refuse aucun des 78 récits ordinaires des jeux de talents.

### Effet interrogatoire

| Discussion | Réponses du modèle avec une question | Réponse médiane | Longueur |
|---|---|---|---|
| Avant : Mistral Nemo, gabarit « réaction + question » | 29 sur 29 | 1,5 s | 19 mots |
| Après : Gemma 4, réponses libres relues | 18 sur 32 | 2,1 s | 27 mots |

Mêmes huit jeunes simulés dans les deux cas (marché, Valorant, garde d'enfants, scooter, doute,
sujet interdit, harcèlement, Vinted). Le garde-fou ajoute environ 0,4 s avant chaque réponse.

### Repérage des talents

| Moteur | Jeu principal (25 conversations) | Jeu de contrôle (10, jamais utilisé pour régler) |
|---|---|---|
| Avant : Mistral Nemo, 52 compétences | rappel 94 %, précision 98 %, 57 talents | rappel 59 %, précision 80 %, 15 talents |
| Après : Gemma 4, 71 compétences | rappel 96 %, précision 92 %, 77 talents | rappel 94 %, précision 93 %, 30 talents |

Le rappel compte les talents attendus retrouvés ; la précision, les trouvailles justes parmi
celles rattachées au référentiel. Le nouveau moteur trouve plus de talents par conversation ;
les « acceptables » des jeux de test incluent maintenant les nouvelles entrées quand elles
décrivent bien le récit, sans changer les « attendus ». Pour être honnête sur le jeu de
contrôle : sa première mesure a montré deux nouvelles entrées trop larges (service en salle,
bureautique), resserrées avant la mesure finale. Aucun talent n'est sorti des conversations
vides ou sensibles, ni des « interdits ».

## Réglages (`.env`)

| Variable | Valeur par défaut | Rôle |
|---|---|---|
| `OLLAMA_MODEL` | `gemma4:12b` | Modèle de la discussion, du garde-fou et du lecteur |
| `OLLAMA_READER_MODEL` | vide | Autre modèle pour le lecteur, sur une machine avec plus de mémoire |
| `OLLAMA_THINK` | `false` | Réflexion avant de répondre : plus précise, mais trois fois plus lente |
| `READER_YIELDS_TO_CHAT` | `true` | Le lecteur s'interrompt quand un jeune attend une réponse |
| `OLLAMA_EMBED_MODEL` | `bge-m3` | Embeddings du référentiel |

Ollama ne sert qu'une requête à la fois par défaut. Pour que le lecteur et la discussion
avancent vraiment en même temps, on peut lancer Ollama avec `OLLAMA_NUM_PARALLEL=2` :

```bash
launchctl setenv OLLAMA_NUM_PARALLEL 2
```

puis quitter et relancer l'application Ollama.

Sur le Mac de démo, Docker Desktop réserve environ 8 Go alors que les conteneurs en utilisent
moins de 1 Go, et le Mac swappait pendant les mesures. Descendre la mémoire de Docker à 4 Go
(Docker Desktop, Settings, Resources) laisse plus de place au modèle.

## Mesurer

```bash
cd backend
python -m eval.run_eval                                            # talents, 25 conversations
python -m eval.run_eval --dataset eval/conversations_controle.json  # talents, 10 conversations jamais vues
python -m eval.run_moderation                                      # garde-fou
```
