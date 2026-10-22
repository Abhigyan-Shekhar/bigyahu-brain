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
        if any(p.is_symlink() for p in (source, *source.parents) if p != root) or not source.resolve().is_relative_to(root):
            raise ValueError("Package inputs must be ordinary files inside the source root")
        destination = plugin / destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))

    # Every shipped input requires an explicit, reviewed manifest entry. Never
    # discover inputs by walking a developer's checkout.
    files = json.loads((root / "packaging/company-brain/files.json").read_text())
    for source, destination in files.items():
        for name in (source, destination):
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError("Package manifest paths must stay inside their root")
            if any(part.startswith(".") or part in {"data", "__pycache__"} for part in path.parts):
                raise ValueError("Local or hidden state cannot be packaged")
            if path.name.endswith((".local.yaml", ".local.yml", ".pyc", ".pem", ".key")):
                raise ValueError("Sensitive or generated files cannot be packaged")
        copy(source, destination)

    # The installed CLI also supports the legacy overlay. Generate it from the
    # portable manifests so identities and launch commands cannot drift.
    legacy = {k: manifest[k] for k in ("name", "version", "description")}
    legacy.update({"skills": "./skills/", "mcpServers": "./mcp.json", "requires_local_executor": True})
    legacy["extensions"] = {"com.openai": {"onboardingSkill": manifest["extensions"]["com.openai"]["onboardingSkill"]}}
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
