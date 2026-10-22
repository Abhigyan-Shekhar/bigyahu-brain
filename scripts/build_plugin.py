"""Build a source-only desktop plugin ZIP and local marketplace from an allowlist."""

import argparse
import hashlib
import json
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_plugin(output, root=ROOT):
    root, output = Path(root).resolve(), Path(output).resolve()
    manifest = json.loads((root / "packaging/company-brain/plugin.json").read_text())
    project = tomllib.loads((root / "pyproject.toml").read_text())
    if manifest["version"] != project["project"]["version"]:
        raise ValueError("Plugin and Python package versions must match")
    output.mkdir(parents=True, exist_ok=False)
    marketplace = output / "marketplace"
    plugin = marketplace / "plugins/company-brain"

    def copy(source, destination):
        source = root / source
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError("Package inputs must be ordinary files inside the source root")
        destination = plugin / destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))

    for name in ("plugin.json", "mcp.json"):
        copy("packaging/company-brain/" + name, name)
    for name in ("pyproject.toml", "uv.lock", "README.md", "docs/plugin.md", "docs/codex.md",
                 "config/brain.example.yaml", "scripts/run_lite.py", "scripts/verify_codex_discovery.py"):
        copy(name, name)
    for directory in ("src/brain", "skills/company-brain", "skills/company-brain-setup"):
        for source in sorted((root / directory).rglob("*")):
            if source.is_file() and source.suffix in {".py", ".md", ".yaml"}:
                copy(source.relative_to(root), source.relative_to(root))

    # The installed CLI also supports the legacy overlay. Generate it from the
    # portable manifests so identities and launch commands cannot drift.
    legacy = {k: manifest[k] for k in ("name", "version", "description")}
    legacy.update({"skills": "./skills/", "mcpServers": "./mcp.json", "requires_local_executor": True})
    legacy["interface"] = manifest["extensions"]["com.openai"]["interface"]
    (plugin / ".codex-plugin").mkdir()
    (plugin / ".codex-plugin/plugin.json").write_text(json.dumps(legacy, indent=2) + "\n", encoding="utf-8", newline="\n")
    catalog = {
        "name": "company-brain-local", "interface": {"displayName": "Company Brain"},
        "plugins": [{"name": "company-brain", "source": {"source": "local", "path": "./plugins/company-brain"},
                     "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                     "category": "Developer Tools"}],
    }
    (marketplace / ".agents/plugins").mkdir(parents=True)
    (marketplace / ".agents/plugins/marketplace.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8", newline="\n")
    archive = output / f"company-brain-{manifest['version']}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for source in sorted(plugin.rglob("*")):
            if source.is_file():
                info = zipfile.ZipInfo("company-brain/" + source.relative_to(plugin).as_posix(), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, source.read_bytes())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(checksum + "  " + archive.name + "\n", encoding="utf-8", newline="\n")
    return {"plugin": str(plugin), "marketplace": str(marketplace), "archive": str(archive), "sha256": checksum}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/company-brain-plugin")
    args = parser.parse_args()
    print(json.dumps(build_plugin(args.output), indent=2))


if __name__ == "__main__":
    main()
