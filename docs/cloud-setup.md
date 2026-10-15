# FalkorDB Cloud provisioning and integration

Status: configuration prepared and offline-tested only. No Cloud instance,
endpoint, credentials, TLS handshake, Cypher execution or graph sync is verified.
The working Codex registration is preserved. Do not repair Podman.

## Provision this

1. Sign in at https://app.falkordb.cloud/ and create a dedicated development
   instance named `bigyahu-brain-dev` (suggested name, not an existing instance).
2. Choose a TLS-enabled standalone deployment. The current official comparison
   says TLS starts at Startup; Free has no TLS. Startup is advertised from
   $0.100 per memory GB/hour (about $73/month for 1 GB at 730 hours). Confirm
   actual price, region and size in the console before purchasing. We have not
   tested memory requirements; the smallest TLS-enabled instance is a starting
   point, not a capacity guarantee. No cluster or high availability is needed.
3. Select an available region near this development machine. Use a public TLS
   endpoint reachable from this machine; a private VPC-only endpoint will not
   work without additional network connectivity. If the console offers network
   access rules, permit this machine's current egress address.
4. Wait for the deployment to become ready. Obtain the database DNS hostname,
   database port, database username and password from its connection details.
   The Browser web URL and Cloud account login are not database connection details.
5. Use a dedicated development database account with graph read/write/index
   permissions for `org_demo` and `private_demo_operator`. The Python driver also
   probes server INFO/cluster status. Full-text procedures must be supported.
   The opt-in fixture tests use `org_demo` and a random `private_test_*` graph and
   delete their fixtures afterwards, so run them only on this development instance
   with permission to create/delete test graphs. We will verify exact ACL/version
   compatibility against the actual deployment, not assume it.

Official references (checked 15 October 2026):
- https://docs.falkordb.com/cloud/
- https://docs.falkordb.com/cloud/tiers/startup
- https://falkordb-py.readthedocs.io/en/stable/falkordb.html

The general Cloud and tier pages were accessible. The detailed console connection
page could not be fetched; use the console's actual supplied fields rather than
assuming a particular UI label, username, port, or server version.

## Provide these details

Nonsecret: database hostname, port, username, TLS requirement, provider/region,
server version if shown, and whether a custom CA PEM is required. Optionally
provide the Browser URL for later inspection.

Secret: save the database password locally, never in chat, YAML, shell command
arguments, Codex settings, Git, or recorded traces. Suggested file:
`<project>/.secrets/falkordb-password`. Create its directory with mode 0700 and
write the password using a local editor or password manager; set file mode 0600.
`.secrets/` is ignored by Git. Tell Codex only its absolute path. The password
file must contain just the password (one trailing newline is accepted). The
application rejects missing, empty, oversized or group/world-accessible files.

If the provider requires a custom CA, save its PEM locally and supply its absolute
path. Otherwise the Python SSL context uses its default trusted certificates.
Certificate verification and hostname matching cannot be disabled by config.
If a different authentication mechanism or mutual TLS is required, stop and
adapt explicitly rather than silently downgrading security.

## Configuration prepared

`config/brain.cloud.example.yaml` contains null endpoint placeholders and an
absolute-path placeholder for the secret; it intentionally cannot connect as-is.
Once actual values exist, merge them into the ignored `config/brain.local.yaml`
while preserving the real repo_root/repo_id/principal. Do not overwrite that
working file with placeholders. The existing Codex registration already points
at it, so no MCP server rename, password environment variable, or launcher
change is needed. Restart the MCP connection after updating it.

The client passes username, password and verified TLS directly to the installed
FalkorDB driver. Non-loopback plaintext connections are rejected. Passwords are
loaded lazily at connection time, not during tool discovery. Remote integration
checks exercise the same transport settings through BRAIN_TEST_CONFIG.

## Run only after provisioning

From the project root:

```sh
export BRAIN_CONFIG="$PWD/config/brain.local.yaml"
export PYTHONPATH="$PWD/src"
uv sync --frozen

# Dedicated development instance only: this creates/deletes fixture graphs.
BRAIN_INTEGRATION=1 BRAIN_TEST_CONFIG="$BRAIN_CONFIG" uv run pytest -q -m integration

# Index the real clean, pinned checkout and public snapshots.
uv run python -m brain sync
uv run python -m brain ingest-snapshots data/sources
```

Verify real symbol counts and 1–2 hop incoming CALLS paths against source files;
then record a Codex `check_change` call before editing. Tests/discovery passing
without a live server do not close those gates. Only an independent human may
approve a source-backed, revision-valid constraint. Then run one real edit and
its relevant tests, before attempting the baseline comparison or recording.
