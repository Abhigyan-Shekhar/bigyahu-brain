"""Automatic conservative extraction from an explicitly consented conversation.

Version 1 extracts verbatim user sentences as candidate facts, not inferred truth.
An explicit semantic_model opts into model selection of literal durable spans.
No trace scraper, assistant assertion promotion or implicit collection.
"""

import re

from .memory import canonical, digest, now


def validate_conversation(payload, consent_digest):
    if (
        not isinstance(payload, dict)
        or set(payload) != {"format", "session", "turns"}
        or payload["format"] != "conversation/1"
    ):
        raise ValueError("Expected conversation/1 envelope")
    if digest(canonical(payload)) != consent_digest:
        raise ValueError("Explicit consent must cover the exact conversation")
    session, turns = payload["session"], payload["turns"]
    if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session):
        raise ValueError("Invalid session identifier")
    if (
        not isinstance(turns, list)
        or not 1 <= len(turns) <= 100
        or len(canonical(payload).encode()) > 1_000_000
    ):
        raise ValueError("Conversation bound exceeded")
    seen = set()
    for turn in turns:
        if (
            not isinstance(turn, dict)
            or set(turn) != {"id", "role", "text"}
            or not isinstance(turn["id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", turn["id"])
            or turn["id"] in seen
            or not isinstance(turn["role"], str)
            or turn["role"] not in {"user", "assistant"}
            or not isinstance(turn["text"], str)
            or not 1 <= len(turn["text"]) <= 12000
        ):
            raise ValueError("Invalid or duplicate conversation turn")
        seen.add(turn["id"])
    return session, turns


def ingest_conversation(memory, payload, consent_digest, semantic_model=None):
    session, turns = validate_conversation(payload, consent_digest)
    if semantic_model:
        from .conversation_semantics import analyze

        # Consent and envelope validation precede any opt-in model invocation.
        analysis = analyze(payload, semantic_model)
        return _ingest_semantic(memory, payload, consent_digest, analysis, semantic_model)
    facts = []
    for turn in turns:
        if turn["role"] != "user":
            continue
        # Preserve literal spans. Questions are not assertions. These proposals
        # still require review; imperative/injected prose has no execution authority.
        for number, span in enumerate(re.finditer(r"[^\n]+", turn["text"])):
            text = span.group().strip()
            if not text or text.endswith("?"):
                continue
            start = span.start() + len(span.group()) - len(span.group().lstrip())
            facts.append(
                {
                    "uid": "conversation:" + digest(canonical([session, turn["id"], number])),
                    "text": text,
                    "sources": [
                        {
                            "uri": f"urn:codex-conversation:{session}:{turn['id']}:chars:"
                            f"{start}:{start + len(text)}",
                            "digest": digest(text),
                        }
                    ],
                }
            )
    if not 1 <= len(facts) <= 200:
        raise ValueError("Expected one to 200 extracted user assertions")
    brain = "private:" + memory.identity.principal
    with memory.lock, memory.db:
        memory.db.execute("BEGIN IMMEDIATE")
        memory.authorize(brain, write=True)
        # The same session/turn is immutable. Corrections use new turn IDs;
        # accidental replay of edited source fails instead of silently refreshing.
        result = [
            memory.put(
                brain, f["text"], f["sources"], f["uid"], collection="conversation:" + session
            )
            for f in facts
        ]
        memory._event(brain, session, "conversation_consent", consent_digest)
    return {
        "brain": brain,
        "items": result,
        "extractor": "verbatim-user-lines/1",
        "binding": False,
        "warnings": ["candidate_assertions_require_review"],
    }


def _ingest_semantic(memory, payload, consent_digest, analysis, model):
    from .conversation_semantics import validate_analysis
    from .memory_graph import entities
    from .memory_links import MemoryLinks

    analysis = validate_analysis(payload, {"items": analysis})
    turns = {t["id"]: t for t in payload["turns"]}
    brain = "private:" + memory.identity.principal
    items, relationships, warnings = [], [], ["model_selected_candidates_require_review"]
    with memory.lock, memory.db:
        memory.db.execute("BEGIN IMMEDIATE")
        memory.authorize(brain, write=True)
        # Only current accepted private records participate in correction matching.
        prior = memory.db.execute(
            "SELECT uid,hash,text FROM records WHERE tenant=? AND brain=? AND state='accepted' "
            "AND (expires='' OR expires>?) ORDER BY uid LIMIT 1001",
            (memory.identity.tenant, brain, now()),
        ).fetchall()
        if len(prior) > 1000:
            raise ValueError("Correction comparison bound exceeded")
        for candidate in analysis:
            turn, start, end = candidate["turn"], candidate["start"], candidate["end"]
            text = turns[turn]["text"][start:end]
            uid = "conversation:" + digest(
                canonical([payload["session"], turn, "semantic/1", start, end])
            )
            proof = [
                {
                    "uri": f"urn:codex-conversation:{payload['session']}:{turn}:chars:{start}:{end}",
                    "digest": digest(text),
                }
            ]
            item = memory.put(
                brain, text, proof, uid, collection="conversation:" + payload["session"]
            )
            metadata = canonical(
                {
                    "hash": item["hash"],
                    "model": model,
                    "kind": candidate["kind"],
                    "entities": sorted(set(candidate["entities"])),
                }
            )
            existing = memory.db.execute(
                "SELECT detail FROM events WHERE tenant=? AND brain=? AND uid=? "
                "AND action='conversation_analysis' ORDER BY rowid DESC LIMIT 1",
                (memory.identity.tenant, brain, uid),
            ).fetchone()
            if existing and existing[0] != metadata:
                raise ValueError("Semantic analysis conflict; use a new turn identifier")
            if not existing:
                memory._event(brain, uid, "conversation_analysis", metadata)
            items.append(item)
            # Require both model classification and an explicit lexical correction cue.
            # Match an unambiguous backticked subject; never guess semantic supersession.
            if candidate["kind"] == "correction" and re.match(
                r"(?i)^(correction|actually|instead|we (?:now|no longer)|change of plan)\b", text
            ):
                subjects = set(entities(text))
                matches = [
                    r for r in prior if r["uid"] != uid and subjects & set(entities(r["text"]))
                ]
                if len(matches) == 1:
                    old = matches[0]
                    relationships.append(
                        MemoryLinks(memory).put(
                            brain, uid, item["hash"], "UPDATES", old["uid"], old["hash"], proof
                        )
                    )
                else:
                    warnings.append("correction_target_unresolved")
        memory._event(brain, payload["session"], "conversation_consent", consent_digest)
    return {
        "brain": brain,
        "items": items,
        "relationships": relationships,
        "extractor": "semantic-spans/1",
        "model": model,
        "binding": False,
        "warnings": sorted(set(warnings)),
    }
