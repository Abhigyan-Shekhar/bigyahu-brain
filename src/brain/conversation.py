"""Automatic conservative extraction from an explicitly consented conversation.

Version 1 extracts verbatim user sentences as candidate facts, not inferred truth.
No LLM, trace scraper, assistant assertion promotion or implicit collection.
"""

import re

from .memory import canonical, digest


def ingest_conversation(memory, payload, consent_digest):
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
    facts, seen = [], set()
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
