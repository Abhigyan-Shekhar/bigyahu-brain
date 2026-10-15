"""Repository-local identities preserve provenance without cross-repo traversal."""


def identity_uid(repo_id, identity):
    return f"{repo_id}:identity:{identity}"
