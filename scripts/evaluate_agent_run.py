"""Evaluate only after the model exits; oracle remains outside its checkout."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--oracle', type=Path, required=True)
    parser.add_argument('--oracle-sha256', required=True)
    args = parser.parse_args()
    completion = json.loads((args.run / 'completion.json').read_text())
    if not completion.get('finished_at'):
        parser.error('agent must exit before evaluation')
    if hashlib.sha256(args.oracle.read_bytes()).hexdigest() != args.oracle_sha256:
        parser.error('oracle hash mismatch')
    if args.oracle.resolve().is_relative_to(args.work.resolve()):
        parser.error('oracle must remain outside the agent checkout')
    output = args.run / 'evaluation'
    output.mkdir(exist_ok=False)
    env = {**os.environ, 'PYTHONPATH': str(args.work / 'src')}
    python = str(args.work / '.venv/bin/python')
    commands = {'oracle': [python, str(args.oracle)],
                'upstream': [python, '-m', 'pytest', '-q', 'test/test_poolmanager.py',
                             'test/with_dummyserver/test_poolmanager.py', 'test/test_util.py',
                             'test/with_dummyserver/test_connectionpool.py',
                             '-k', 'PoolManager or redirect or rewind_body or set_file_position']}
    results = {}
    for name, command in commands.items():
        (output / (name + '-invocation.json')).write_text(json.dumps({'args': command, 'cwd': str(args.work), 'PYTHONPATH': env['PYTHONPATH']}, indent=2) + '\n')
        with (output / (name + '-results.' + ('json' if name == 'oracle' else 'txt'))).open('x') as stream:
            result = subprocess.run(command, check=False, cwd=args.work, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=300)
        results[name + '_exit'] = result.returncode
    oracle = json.loads((output / 'oracle-results.json').read_text())
    assert Path(oracle['import_path']).resolve().is_relative_to((args.work / 'src').resolve())
    results.update(oracle_passed=sum(r['passed'] for r in oracle['results']),
                   oracle_total=len(oracle['results']),
                   bare_pool_passed=sum(r['passed'] for r in oracle['results'] if r['client'] == 'bare_pool'))
    (output / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results))
    return 0 if (results['oracle_exit'] == results['upstream_exit'] == 0
                 and results['oracle_total'] > 0
                 and results['oracle_passed'] == results['oracle_total']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
