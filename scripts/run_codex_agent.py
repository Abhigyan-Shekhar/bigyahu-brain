"""Run one fresh Codex session; preserve all emitted evidence locally."""

import argparse
import datetime
import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path

READONLY = ['get_context', 'check_change', 'trace_decision', 'find_owner']


def git(work, *args):
    return subprocess.check_output(['git', '-C', str(work), *args], text=True)


def build_command(args, output):
    command = ['codex', 'exec', '--ignore-user-config', '--strict-config',
               '--ephemeral', '--json', '--disable', 'plugins', '--disable', 'apps',
               '-m', args.model, '-s', 'workspace-write']
    config = {'model_reasoning_effort': args.reasoning, 'approval_policy': 'never',
              'project_doc_max_bytes': 0, 'web_search': 'disabled'}
    if args.brain_config:
        readonly = READONLY + (["memory_search"] if getattr(args, "memory_search", False) else [])
        prefix = 'mcp_servers.company-brain.'
        config.update({prefix + 'command': str(args.brain_python),
                       prefix + 'args': ['-m', 'brain.mcp_server'],
                       prefix + 'env.BRAIN_CONFIG': str(args.brain_config),
                       prefix + 'env.PYTHONPATH': str(args.brain_src),
                       prefix + 'enabled_tools': readonly,
                       prefix + 'disabled_tools': ['remember'] + (['memory_propose'] if getattr(args, 'memory_search', False) else []),
                       prefix + 'default_tools_approval_mode': 'prompt'})
        config.update({prefix + f'tools.{name}.approval_mode': 'approve'
                       for name in readonly})
    for key, value in config.items():
        command += ['-c', key + '=' + json.dumps(value)]
    return command + ['-C', str(args.work), '-o', str(output / 'agent-final.txt'), '-']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'out', 'task'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--reasoning', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--brain-config', type=Path)
    parser.add_argument('--brain-python', type=Path)
    parser.add_argument('--brain-src', type=Path)
    parser.add_argument('--memory-search', action='store_true', help='Enable read-only memory search in the hybrid arm')
    parser.add_argument('--instructions', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args()
    for key in ('work', 'out', 'task', 'instructions', 'brain_config', 'brain_python', 'brain_src'):
        value = getattr(args, key)
        if value is not None and not value.is_absolute():
            parser.error('--' + key.replace('_', '-') + ' must be absolute')
    if args.brain_config and not (args.brain_python and args.brain_src):
        parser.error('graph arm requires absolute Python and src paths')
    if git(args.work, 'rev-parse', 'HEAD').strip() != args.revision:
        parser.error('checkout revision mismatch')
    if git(args.work, 'status', '--porcelain').strip():
        parser.error('requires a clean checkout')
    if args.brain_config:
        import yaml
        cfg = yaml.safe_load(args.brain_config.read_text())
        if Path(cfg['repo_root']).resolve() != args.work.resolve():
            parser.error('trusted server repo_root must match coding checkout')
    # Refuse reuse. Output stays outside model working directory.
    if args.out.resolve().is_relative_to(args.work.resolve()):
        parser.error('output must be outside coding checkout')
    args.out.mkdir(parents=True, exist_ok=False)
    prompt = args.task.read_text().strip() + '\n\n' + args.instructions.read_text()
    (args.out / 'session-prompt.txt').write_text(prompt)
    command = build_command(args, args.out)
    manifest = {'args': command, 'revision': args.revision, 'model': args.model,
                'reasoning': args.reasoning,
                'started_at': datetime.datetime.now(datetime.UTC).isoformat(),
                'codex_version': subprocess.check_output(['codex', '--version'], text=True).strip(),
                'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'backend_revision': git(args.brain_src.parent, 'rev-parse', 'HEAD').strip()
                    if args.brain_src else None}
    manifest['environment'] = {'platform': platform.platform(),
                               'runner_python': platform.python_version()}
    (args.out / 'runner-invoked.py').write_bytes(Path(__file__).read_bytes())
    if args.brain_config:
        (args.out / 'brain-config.yaml').write_bytes(args.brain_config.read_bytes())
    python = args.work / '.venv/bin/python'
    if python.exists():
        manifest['task_python'] = subprocess.check_output([str(python), '--version'], text=True).strip()
        freeze = subprocess.run([str(python), '-c',
            'import importlib.metadata as m; print("\\n".join(sorted(f"{d.metadata[\"Name\"]}=={d.version}" for d in m.distributions())))'],
            capture_output=True, text=True, check=False)
        (args.out / 'dependencies.txt').write_text(freeze.stdout)
    (args.out / 'invocation.json').write_text(json.dumps(manifest, indent=2) + '\n')
    env = dict(os.environ)
    env.pop('BRAIN_OPERATOR_SESSION', None)
    start = time.monotonic()
    with (args.out / 'trace.jsonl').open('x') as trace, (args.out / 'stderr.txt').open('x') as err:
        try:
            result = subprocess.run(command, check=False, input=prompt, text=True, stdout=trace,
                                    stderr=err, env=env, timeout=args.timeout)
            completion = {'exit_code': result.returncode}
        except subprocess.TimeoutExpired:
            completion = {'exit_code': None, 'error': 'timeout'}
    completion.update(elapsed_seconds=time.monotonic() - start,
                      finished_at=datetime.datetime.now(datetime.UTC).isoformat())
    (args.out / 'completion.json').write_text(json.dumps(completion, indent=2) + '\n')
    (args.out / 'agent.patch').write_text(git(args.work, 'diff', '--binary'))
    with (args.out / 'agent.patch').open('a') as patch:
        for name in git(args.work, 'ls-files', '--others', '--exclude-standard').splitlines():
            result = subprocess.run(['git', 'diff', '--no-index', '--binary', '/dev/null', name],
                                    check=False, cwd=args.work, capture_output=True, text=True)
            patch.write(result.stdout)
    (args.out / 'final-status.txt').write_text(git(args.work, 'status', '--porcelain'))
    events = [json.loads(line) for line in (args.out / 'trace.jsonl').read_text().splitlines()]
    calls = [{'line': n, **event} for n, event in enumerate(events, 1)
             if event.get('item', {}).get('type') == 'mcp_tool_call']
    (args.out / 'mcp-events.json').write_text(json.dumps(calls, indent=2) + '\n')
    (args.out / 'commands.json').write_text(json.dumps([
        {'line': n, **event} for n, event in enumerate(events, 1)
        if event.get('item', {}).get('type') == 'command_execution'], indent=2) + '\n')
    completion['turn_completed'] = any(e.get('type') == 'turn.completed' for e in events)
    (args.out / 'completion.json').write_text(json.dumps(completion, indent=2) + '\n')
    print(json.dumps(completion))
    return 0 if completion['exit_code'] == 0 and completion['turn_completed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
