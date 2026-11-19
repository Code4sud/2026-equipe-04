"""Mesure du repérage des talents sur des conversations réalistes, avec l'Ollama local.

    cd backend && python -m eval.run_eval              # nouveau moteur, message par message
    cd backend && python -m eval.run_eval --baseline   # ancienne méthode (une question à Mistral)
    cd backend && python -m eval.run_eval --only capture-mecanique -v
    cd backend && python -m eval.run_eval --dataset eval/conversations_controle.json

Rappel = talents attendus trouvés / talents attendus.
Précision = trouvailles attendues ou acceptables / trouvailles rattachées au référentiel.
Les talents « libres » (hors référentiel) sont listés à part pour relecture.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from app.services.embeddings import OllamaEmbedder, ReferentielIndex
from app.services.guardrails import Guardrails, find_quote
from app.services.llm import OllamaClient
from app.services.prompts import PromptLibrary
from app.services.referentiel import Referentiel
from app.services.talent_detector import PROPOSAL_MATCH, PROPOSAL_SCHEMA, TalentDetector

BACKEND = Path(__file__).resolve().parent.parent
DATASET = Path(__file__).with_name("conversations.json")


def build(url: str, model: str, embed_model: str):
    prompts = PromptLibrary(str(BACKEND / "prompts"))
    guardrails = Guardrails(prompts)
    referentiel = Referentiel(prompts)
    llm = OllamaClient(url, model)
    index = ReferentielIndex(OllamaEmbedder(url, embed_model), referentiel) if embed_model else None
    return TalentDetector(llm, prompts, guardrails, referentiel, index), llm, prompts, guardrails


def run_engine(detector, guardrails, conversation) -> list:
    """Comme en production : une analyse après chaque message, avec les talents déjà trouvés."""
    found, known = [], []
    for index, text in enumerate(conversation["messages"]):
        message = {"id": f"x{index}", "role": "user", "content": text}
        if guardrails.is_sensitive(text):
            continue
        for finding in detector.detect([message], known):
            if finding.entry_id and finding.entry_id in {f.entry_id for f in found}:
                continue
            found.append(finding)
            known.append(finding.name)
    return found


def run_baseline(detector, llm, guardrails, conversation) -> list:
    """Ancienne méthode : un seul appel avec l'ancien prompt, sur toute la conversation."""
    old_prompt = subprocess.run(
        ["git", "show", "46e9e94:backend/prompts/extraction.md"],
        cwd=BACKEND, capture_output=True, text=True, check=True,
    ).stdout
    messages = [{"id": f"x{i}", "content": t} for i, t in enumerate(conversation["messages"])]
    lines = [f"[m{i}] {m['content']}" for i, m in enumerate(messages, start=1)]
    answer = llm.generate_json(
        old_prompt, "Messages écrits par le jeune :\n" + "\n".join(lines) + "\n\nCompétences déjà repérées, à ne pas répéter : aucune",
        PROPOSAL_SCHEMA,
    )
    found = []
    for proposal in answer.get("competences", [])[:3]:
        match = find_quote(str(proposal.get("citation", "")), messages)
        name = str(proposal.get("nom", ""))
        if match is None or guardrails.review_skill(name, proposal.get("description", ""), match.quote) is None:
            continue
        entry = None
        if detector.index:
            ranked = detector.index.rank(detector.index.embedder.embed([f"{name}. {proposal.get('description', '')}"]))[0]
            best, score = max(ranked.items(), key=lambda item: item[1])
            entry = best if score >= PROPOSAL_MATCH else None
        found.append(type("F", (), {"name": name, "entry_id": entry, "quote": match.quote, "category": proposal.get("categorie"), "signals": ("ancien",)}))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "gemma4:12b"))
    parser.add_argument("--embed-model", default=os.environ.get("OLLAMA_EMBED_MODEL", "bge-m3"))
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--only")
    parser.add_argument("--dataset", default=str(DATASET), help="par défaut conversations.json ; contrôle : conversations_controle.json")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--json", help="écrit le détail dans ce fichier")
    args = parser.parse_args()

    detector, llm, _, guardrails = build(args.url, args.model, args.embed_model)
    data = json.loads(Path(args.dataset).read_text(encoding="utf-8"))["conversations"]
    if args.only:
        data = [c for c in data if c["id"] == args.only]

    expected_total = expected_found = matched = correct = 0
    false_on_empty = forbidden = 0
    report = []
    started = time.time()
    for conversation in data:
        t0 = time.time()
        if args.baseline:
            found = run_baseline(detector, llm, guardrails, conversation)
        else:
            found = run_engine(detector, guardrails, conversation)
        ids = {f.entry_id for f in found if f.entry_id}
        gold = set(conversation["attendus"])
        ok = gold | set(conversation.get("acceptables", []))
        hit = gold & ids
        expected_total += len(gold)
        expected_found += len(hit)
        matched += len(ids)
        correct += len(ids & ok)
        if not gold and found:
            false_on_empty += 1
        forbidden += len(ids & set(conversation.get("interdits", [])))
        row = {
            "id": conversation["id"],
            "secondes": round(time.time() - t0, 1),
            "rappel": f"{len(hit)}/{len(gold)}",
            "manques": sorted(gold - ids),
            "hors_attendus": sorted(ids - ok),
            "talents": [
                {"nom": f.name, "ref": f.entry_id, "categorie": f.category, "citation": f.quote, "signaux": list(f.signals)}
                for f in found
            ],
        }
        report.append(row)
        print(f"{row['id']:<20} rappel {row['rappel']:<5} manques {row['manques']} hors {row['hors_attendus']} ({row['secondes']} s)")
        if args.verbose:
            for talent in row["talents"]:
                print(f"    - {talent['nom']} [{talent['ref']}/{talent['categorie']}] « {talent['citation']} » {talent['signaux']}")
        sys.stdout.flush()

    recall = expected_found / expected_total if expected_total else 0
    precision = correct / matched if matched else 0
    print(
        f"\nRappel {expected_found}/{expected_total} = {recall:.0%} · précision {correct}/{matched} = {precision:.0%}"
        f" · conversations sans talent attendu mais avec trouvaille : {false_on_empty}"
        f" · interdits : {forbidden} · {time.time() - started:.0f} s"
    )
    if args.json:
        Path(args.json).write_text(json.dumps({"recall": recall, "precision": precision, "rows": report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
