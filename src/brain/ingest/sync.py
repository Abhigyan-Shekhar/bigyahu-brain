import hashlib
import tokenize

from .ast_parser import parse
from .codeowners import owners_for, read_rules
from .git_parser import clean, commits, git, revision


def sync(store):
    cfg = store.cfg
    if not clean(cfg.repo_root):
        raise ValueError("Sync requires a clean committed checkout")
    sha = revision(cfg.repo_root)
    files = git(cfg.repo_root, "ls-files", "-z").split("\0")
    # Parse everything before modifying the graph, including encoding validation.
    modules = {}
    for path in files:
        if not path.endswith(".py") or any(
            p in path.split("/") for p in ("vendor", "build", ".venv", "node_modules")
        ):
            continue
        cfg.path(path)
        with tokenize.open(cfg.repo_root / path) as f:
            modules[path] = parse(f.read(), path, cfg.repo_id, sha)
    store.bootstrap()
    store.upsert(
        "Project", cfg.repo_id, {"repo_id": cfg.repo_id, "url": cfg.repo_url, "syncing": True}
    )
    # Readers refuse incomplete syncs. Old revision nodes remain for provenance.
    store.query("MATCH (s:Symbol {repo_id:$repo})-[r:CALLS]->() DELETE r", {"repo": cfg.repo_id})
    store.query(
        "MATCH (p)-[r:CODEOWNER_OF]->(f:File {repo_id:$repo}) DELETE r", {"repo": cfg.repo_id}
    )
    store.query(
        "MATCH (n {repo_id:$repo}) WHERE n:File OR n:Symbol SET n.current=false",
        {"repo": cfg.repo_id},
    )
    location, rules = read_rules(cfg.repo_root)
    count = 0
    for path in files:
        if not path or not (cfg.repo_root / path).is_file():
            continue
        cfg.path(path)
        file_uid = f"{cfg.repo_id}@{sha}:{path}"
        store.upsert(
            "File",
            file_uid,
            {
                "repo_id": cfg.repo_id,
                "path": path,
                "revision": sha,
                "current": True,
                "digest": hashlib.sha256((cfg.repo_root / path).read_bytes()).hexdigest(),
            },
        )
        store.edge(cfg.repo_id, "CONTAINS", file_uid)
        match = owners_for(path, rules)
        if match:
            source_uid = f"{cfg.repo_id}@{sha}:{location}:L{match['line']}"
            store.upsert(
                "Source",
                source_uid,
                {
                    "repo_id": cfg.repo_id,
                    "revision": sha,
                    "uri": f"{cfg.repo_url}/blob/{sha}/{location}#L{match['line']}",
                    "excerpt": match["pattern"] + " " + " ".join(match["owners"]),
                },
            )
            for owner in match["owners"]:
                uid = f"github:{owner}"
                store.upsert("Team" if "/" in owner else "Person", uid, {"name": owner})
                store.edge(
                    uid,
                    "CODEOWNER_OF",
                    file_uid,
                    {
                        "source_uid": source_uid,
                        "pattern": match["pattern"],
                        "confidence": "explicit",
                    },
                )
        module = modules.get(path)
        if module:
            for s in module.symbols:
                store.upsert("Symbol", s["uid"], {**s, "repo_id": cfg.repo_id})
                store.edge(file_uid, "DECLARES", s["uid"])
                count += 1
            for call in module.calls:
                store.edge(
                    call["source"],
                    "CALLS",
                    call["target"],
                    {
                        "confidence": call["confidence"],
                        "method": "python_ast",
                        "line": call["line"],
                        "source_uid": file_uid,
                    },
                )
    for commit in commits(cfg.repo_root):
        uid = f"{cfg.repo_id}:commit:{commit['sha']}"
        person = "git:" + hashlib.sha256(commit["email"].encode()).hexdigest()
        store.upsert("Person", person, {"name": commit["name"], "identity_basis": "git_author"})
        store.upsert(
            "Commit",
            uid,
            {"sha": commit["sha"], "timestamp": commit["timestamp"], "repo_id": cfg.repo_id},
        )
        source = uid + ":source"
        store.upsert(
            "Source",
            source,
            {
                "repo_id": cfg.repo_id,
                "revision": commit["sha"],
                "uri": f"{cfg.repo_url}/commit/{commit['sha']}",
                "excerpt": commit["body"],
            },
        )
        store.edge(uid, "SUPPORTS", source)
        store.edge(person, "AUTHORED", uid)
        for path in commit["files"]:
            store.edge(uid, "MODIFIES", f"{cfg.repo_id}@{sha}:{path}")
    if sha != revision(cfg.repo_root) or not clean(cfg.repo_root):
        raise ValueError("Checkout changed during sync; graph remains unavailable until rerun")
    store.query(
        "MATCH (p:Project {uid:$repo}) SET p.last_completed_sync_sha=$sha, p.syncing=false",
        {"repo": cfg.repo_id, "sha": sha},
    )
    return {
        "revision": sha,
        "files": len(files),
        "symbols": count,
        "unresolved_calls": sum(len(m.unresolved) for m in modules.values()),
    }
