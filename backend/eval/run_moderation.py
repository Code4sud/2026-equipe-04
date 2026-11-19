"""Mesure du garde-fou des sujets hors cadre, avec l'Ollama local.

    cd backend && python -m eval.run_moderation                 # modèle de OLLAMA_MODEL
    cd backend && python -m eval.run_moderation --model qwen3.5:9b

1. Jeu étiqueté (eval/moderation.json) : sexe, actes illégaux, violence, haine, confidences de
   violences subies, détresse, et pièges (« j'ai tué le game »). Les cas « ambigu » sont
   affichés sans compter.
2. Tous les messages des conversations de test des talents : des récits ordinaires, aucun ne
   doit être refusé.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from app.services.llm import OllamaClient
from app.services.moderation import Moderator
from app.services.prompts import PromptLibrary

BACKEND = Path(__file__).resolve().parent.parent
TO_CLASS = {"ok": "ok", "sexuel": "interdit", "illegal": "interdit", "violence": "interdit",
            "haine": "interdit", "victime": "victime", "detresse": "detresse"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "gemma4:12b"))
    args = parser.parse_args()

    prompts = PromptLibrary(str(BACKEND / "prompts"))
    moderator = Moderator(OllamaClient(args.url, args.model), prompts)

    data = json.loads((BACKEND / "eval" / "moderation.json").read_text(encoding="utf-8"))["messages"]
    good = total = 0
    timings = []
    for item in data:
        started = time.time()
        verdict = moderator.check(item["texte"])
        timings.append(time.time() - started)
        got = TO_CLASS[verdict.category]
        if item["attendu"] == "ambigu":
            print(f"  ~ {got:<9} {item['texte']}")
            continue
        total += 1
        if got == item["attendu"]:
            good += 1
        else:
            print(f"  ✗ attendu {item['attendu']:<9} obtenu {verdict.category} ({verdict.source}) {item['texte']}")
    timings.sort()
    print(
        f"Jeu étiqueté : {good}/{total} = {good / total:.0%} · médiane {timings[len(timings) // 2]:.2f} s"
        f" · max {timings[-1]:.2f} s"
    )

    stories = []
    for name in ("conversations.json", "conversations_controle.json"):
        for conversation in json.loads((BACKEND / "eval" / name).read_text(encoding="utf-8"))["conversations"]:
            stories.extend(conversation["messages"])
    refused = [text for text in stories if moderator.check(text).forbidden]
    print(f"Récits ordinaires refusés à tort : {len(refused)}/{len(stories)}")
    for text in refused:
        print(f"  ✗ {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
