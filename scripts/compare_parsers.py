"""Run pinned deterministic parsers on synthetic code/docs and public PR excerpts.

GraphRAG's semantic LLM extraction is a separate comparison, not silently replaced
with token chunking. This report labels precisely the components exercised.
"""

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from brain.ingest.ast_parser import parse
from brain.ingest.imports import resolve_imports
from brain.memory import digest
from brain.memory_ingest import document_sections

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphify-root", type=Path, required=True)
    parser.add_argument("--graphrag-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from graphify.extract import extract
    from graphrag_chunking.token_chunker import TokenChunker

    samples = {
        "base.py": "def target(): return 1\nclass Base:\n def inherited(self): return target()\n",
        "caller.py": "from base import target, Base\ndef caller(): return target()\nclass Child(Base):\n def run(self): return self.inherited()\n",
        "guide.md": "# Upload replay\nPreserve body discard (#5161).\n`base.target` handles input.\n\n```python\n# not a heading\n```\n",
        "guide.rst": "Upload replay\n=============\nPreserve body discard (#5161).\n:func:`~base.target`\n",
    }
    public = json.loads((ROOT / "data/sources/urllib3/work.json").read_text())
    for record in public:
        samples[f"pr-{record['number']}.md"] = f"# {record['title']}\n\n{record['body'] or ''}\n"
    report = {
        "scope": "deterministic_parser_components_only",
        "inputs": {p: digest(t) for p, t in samples.items()},
        "graphify_revision": subprocess.check_output(
            ["git", "-C", str(args.graphify_root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "graphrag_revision": subprocess.check_output(
            ["git", "-C", str(args.graphrag_root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "results": {},
        "limits": [
            "Small representative fixtures, not a parser accuracy benchmark",
            "Graphify deterministic extraction only; semantic model pass not run",
            "GraphRAG token chunking only; entity extraction and community summaries not run",
            "Shared Unicode-codepoint tokenizer isolates chunking mechanics; not a model tokenizer comparison",
        ],
    }
    start = time.perf_counter()
    modules = {
        p: parse(text, p, "benchmark", "fixture")
        for p, text in samples.items()
        if p.endswith(".py")
    }
    resolve_imports(modules, {p: samples[p] for p in modules})
    report["results"]["company_brain"] = {
        "symbols": sum(len(m.symbols) for m in modules.values()),
        "resolved_calls": sum(len(m.calls) for m in modules.values()),
        "unresolved_calls": sum(len(m.unresolved) for m in modules.values()),
        "document_sections": {
            p: len(list(document_sections(p, t)))
            for p, t in samples.items()
            if not p.endswith(".py")
        },
        "elapsed_ms": (time.perf_counter() - start) * 1000,
    }
    with tempfile.TemporaryDirectory(prefix="parser-comparison-") as directory:
        root = Path(directory)
        for relative, text in samples.items():
            (root / relative).write_text(text)
        start = time.perf_counter()
        result = extract([root / p for p in samples], root=root, cache_root=root, parallel=False)
        from collections import Counter

        report["results"]["graphify"] = {
            "nodes": len(result["nodes"]),
            "edges": len(result["edges"]),
            "relations": dict(Counter(e.get("relation", "unknown") for e in result["edges"])),
            "source_files": sorted({Path(n.get("source_file", "")).name for n in result["nodes"]}),
            "elapsed_ms": (time.perf_counter() - start) * 1000,
        }
    start = time.perf_counter()
    chunker = TokenChunker(
        size=1000,
        overlap=100,
        encode=lambda t: list(map(ord, t)),
        decode=lambda ids: "".join(map(chr, ids)),
    )
    report["results"]["graphrag_chunking"] = {
        "chunks": {p: len(chunker.chunk(t)) for p, t in samples.items()},
        "elapsed_ms": (time.perf_counter() - start) * 1000,
        "semantic_extraction": "not_run",
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["results"], indent=2))


if __name__ == "__main__":
    main()
