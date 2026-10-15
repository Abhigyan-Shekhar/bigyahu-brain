# Trace exposure and retrieval consistency remediation

## Exposure confirmed and contained

The repository was public when checked on 2026-10-16 (India time). Raw agent traces and environment records were tracked in Git. Earlier wording saying the raw records were withheld was incorrect. The owner-visible GitHub API now reports private visibility and zero forks. Anonymous requests to the repository and the reported raw trace return 404. This does not remove existing clones, caches or historical objects.

A scan of all four original commits covered 406 reachable Git objects, including all blobs and commit metadata. Gitleaks 8.30.1, downloaded from its official release and checksum-verified, found zero secret detections with redacted output. A separate history audit found local home paths in 47 blob versions, local temporary paths in 86, session metadata in 26 and email addresses in 12, plus commit-author/committer email metadata. These are counts of blob versions, not unique people. Three credential-shaped URL matches are in a public advisory/example and test material; no active credential was identified. Automated scans are not proof that no secret exists.

Raw findings and local backups stay in the ignored `.secrets/` directory; they contain no emitted matched secret values. Do not publish them. Rotate/revoke any credential subsequently identified as exposed before relying on Git cleanup.

## Current-tree prevention

Local experiment, validation and runtime/demo records are ignored and removed from tracking. Their files remain intact locally, including the negative controls and failed attempts. Reviewed exports live under `docs/demo/`; they contain explicit failure results and source provenance. No raw trace is copied into that directory.

Before committing or publishing, run:

```sh
python scripts/check_publication.py --history
```

The same guard runs in the read-only publication-boundary GitHub Actions workflow.
It reads the Git index and every commit tree reachable from HEAD, rejecting local record directories, runtime trace names, machine-specific paths and common credential shapes. CI fetches full history; a shallow clone fails closed because it cannot prove earlier records are absent. This prevents a later merge from reintroducing deleted records through old ancestry. It does not replace a dedicated secret scanner or binary/export review. Tests exercise rejection and a safe provenance-backed export. Never force-add ignored raw records.

The operator approved and the history rewrite was applied on 2026-10-16 (India time), replacing master `0142e74` with `5ef5536`. A fresh GitHub mirror verified six rewritten commits and 90 historical blobs: raw-record paths and machine-specific home/temp paths were absent, the current source tree was identical, and Gitleaks found zero secret detections. Original non-noreply author/committer emails were replaced with a placeholder while public names and verified account noreply identities were retained.

The repository remains private. Anonymous historical raw trace URLs returned 404, but an old commit remained retrievable through the owner-authenticated GitHub API. Server-side object purging is therefore not confirmed. A Support-request draft was prepared locally and has not been sent. The local original checkout, experiment records and backup bundle were preserved; do not merge or push old ancestry back into the cleaned history. Current follow-up commits may update documentation/guards without changing the reviewed rewrite result.

GitHub documents that rewritten commits may remain in clones, cached commit views or PR references. Support may be needed for sensitive cached data; no promise of complete erasure is made. References: [removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository), [Gitleaks](https://github.com/gitleaks/gitleaks).

## Repository-local identities

People and CODEOWNERS teams now carry `repo_id` and repository-scoped UIDs. Their public identity/provenance is kept separately as `identity_uid` and `identity_basis`. Assigning a single repo_id to a formerly shared global node would overwrite another repository's ownership context, so the fix creates local identities instead.

Sync rebuilds ownership edges, detaches legacy global author edges only from this repository's commits, and creates scoped author edges. Snapshot re-ingestion similarly migrates legacy reviewer edges for the PRs actually re-ingested. Other repositories and private graphs are not rewritten. Existing orphan legacy nodes may remain inaccessible; resync/re-ingest each affected repository rather than relaxing traversal filters.

`get_context` traverses recorded edges in both directions, bounded to the existing two hops and result limits. Each returned path now includes `directions` to distinguish incoming from outgoing edges. Every path node still must belong to the configured repository. `find_owner` applies the same repository restriction to people and teams. Tool names and parameters are unchanged.

## Source-backed PR references

The importer extracts explicit same-repository issue mentions from PR bodies and recorded discussions: `#number`, `owner/repo#number`, or exact GitHub issue URLs. It creates `PR → REFERENCES → Issue` only when the target Issue already exists in the same repository and graph. All records are inserted before references, so snapshot order does not matter. Missing targets are returned as bounded `missing_issue_references`; no placeholder issue or resolution edge is invented. Foreign repositories and PR-only number matches are excluded.

Edges carry source IDs, `explicit_text_reference` confidence, an untrusted-mention basis and `resolution_verified=false`. Mentioning or even saying “Fixes” in untrusted text is not independently verified resolution or decision approval. Re-ingesting a PR replaces only references derived by this importer; unrelated relationships are retained.

Issue lookups can traverse incoming PR references to affected files and receive the referring PR's source. PR lookups can receive the referenced issue source. Every excerpt retains provenance and untrusted/non-binding status; the same source and character bounds apply. Private data and foreign graph paths remain excluded.

## Verification

The full real FalkorDBLite suite passed **81 tests**, including owner/team/author/reviewer traversal, reverse issue→PR→file paths, missing/foreign references, scoped identities across two repositories, and STDIO evidence delivery. The first run had one test assertion selecting the lexically first provenance source rather than the PR body; primary provenance now prefers the body when present, retaining discussion source IDs too. Ruff and diff checks pass. No real decision was created or approved.

The demo's historical 70-test count remains a statement about the recorded demo, not a current suite total. Local measured logs are under the ignored validation directory.
