"""Read saved experiments without executing agents or rewriting historical outputs."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def audit(root, excluded=()):
    def eligible(path):
        return not any(path.resolve().is_relative_to(p.resolve()) for p in excluded)

    inventory = {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob('*'))
                 if p.is_file() and '.venv' not in p.parts and eligible(p)}
    runs = []
    for trace in sorted(root.rglob('*trace.jsonl')):
        if not eligible(trace):
            continue
        directory = trace.parent
        events, parse_errors = [], []
        for line, raw in enumerate(trace.read_text().splitlines(), 1):
            try:
                events.append((line, json.loads(raw)))
            except json.JSONDecodeError:
                parse_errors.append(line)
        calls = []
        for line, event in events:
            item = event.get('item', {})
            if item.get('type') == 'mcp_tool_call':
                calls.append({'line': line, 'event': event})
        prompt = directory / 'session-prompt.txt'
        if not prompt.exists():
            prompt = directory.parent / 'session-prompt.txt'
        if not prompt.exists():
            prompt = directory / 'prompt.txt'
        manifest = directory / 'frozen-manifest.json'
        if not manifest.exists():
            manifest = directory.parent / 'frozen-manifest.json'
        if not manifest.exists():
            manifest = directory / 'run-manifest.json'
        completion = read(directory / 'completion.json', {})
        oracle = read(directory / 'oracle-results.json', {})
        results = oracle.get('results', []) if isinstance(oracle, dict) else []
        runs.append({
            'run': str(directory.relative_to(root)),
            'trace': trace.name,
            'completion': completion,
            'turn_completed': any(e.get('type') == 'turn.completed' for _, e in events),
            'errors': [e for _, e in events if e.get('type') in ('error', 'turn.failed')],
            'parse_error_lines': parse_errors,
            'manifest': read(manifest, {}),
            'invocation': read(directory / 'invocation.json', {}),
            'prompt': prompt.read_text() if prompt.exists() else None,
            'environment': read(directory / 'environment.json', {}),
            'dependencies_sha256': digest(directory / 'dependencies.txt')
                if (directory / 'dependencies.txt').exists() else None,
            'patch_sha256': digest(directory / 'agent.patch')
                if (directory / 'agent.patch').exists() else None,
            'patch_bytes': (directory / 'agent.patch').stat().st_size
                if (directory / 'agent.patch').exists() else 0,
            'mcp_events': calls,
            'oracle_passed': sum(r['passed'] for r in results),
            'oracle_total': len(results),
            'upstream_tail': (directory / 'upstream-results.txt').read_text()[-1200:]
                if (directory / 'upstream-results.txt').exists() else None,
        })
    return {'inventory_sha256': inventory, 'runs': runs,
            'note': 'Local-only audit. Exact prompts, arguments and model-visible responses; not sanitized for publication.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--exclude', type=Path, action='append', default=[])
    args = parser.parse_args()
    # Exclusive creation prevents accidental replacement of an audit.
    result = audit(args.root.resolve(), args.exclude)
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
