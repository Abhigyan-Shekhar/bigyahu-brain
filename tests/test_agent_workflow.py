"""Runner boundaries and evaluator failure reporting, without paid model calls."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(name):
    path = Path(__file__).resolve().parents[1] / 'scripts' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_readonly_codex_configuration(tmp_path):
    runner = module('run_codex_agent')
    args = SimpleNamespace(model='example', reasoning='medium', work=tmp_path,
                           brain_config=tmp_path / 'brain.yaml',
                           brain_python=tmp_path / 'python', brain_src=tmp_path / 'src')
    command = runner.build_command(args, tmp_path / 'out')
    config = dict(value.split('=', 1) for i, value in enumerate(command)
                  if i and command[i - 1] == '-c')
    assert json.loads(config['mcp_servers.company-brain.disabled_tools']) == ['remember']
    assert json.loads(config['mcp_servers.company-brain.enabled_tools']) == runner.READONLY
    assert config['approval_policy'] == '"never"'
    assert command[command.index('-s') + 1] == 'workspace-write'
    assert '--ignore-user-config' in command and '--ephemeral' in command


def test_hybrid_runner_adds_only_readonly_memory_search(tmp_path):
    runner=module('run_codex_agent')
    args=SimpleNamespace(model='example',reasoning='medium',work=tmp_path,
        brain_config=tmp_path/'config',brain_python=tmp_path/'python',brain_src=tmp_path/'src',
        memory_search=True)
    command=runner.build_command(args,tmp_path/'out')
    config=dict(value.split('=',1) for i,value in enumerate(command) if i and command[i-1]=='-c')
    assert json.loads(config['mcp_servers.company-brain.enabled_tools'])==runner.READONLY+['memory_search']
    assert json.loads(config['mcp_servers.company-brain.disabled_tools'])==['remember','memory_propose']


@pytest.mark.parametrize('oracle_exit,upstream_exit,passed,oracle_cases,upstream_tests,skipped,expected', [
    (0, 0, True, 12, 200, 0, 0), (1, 0, False, 12, 200, 0, 1),
    (0, 1, True, 12, 200, 0, 1), (0, 0, False, 12, 200, 0, 1),
    (0, 0, True, 1, 200, 0, 1), (0, 0, True, 13, 200, 0, 1),
    (0, 0, True, 12, 0, 0, 1), (0, 0, True, 12, 3, 3, 1),
])
def test_evaluation_exit_tracks_actual_checks(tmp_path, monkeypatch,
                                              oracle_exit, upstream_exit, passed, oracle_cases,
                                              upstream_tests, skipped, expected):
    evaluator = module('evaluate_agent_run')
    work = tmp_path / 'work'
    work.mkdir()
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'completion.json').write_text(json.dumps({'finished_at': 'now'}))
    oracle = tmp_path / 'oracle.py'
    oracle.write_text('# frozen external check\n')
    digest = evaluator.hashlib.sha256(oracle.read_bytes()).hexdigest()
    monkeypatch.setattr(sys, 'argv', ['evaluate', '--work', str(work), '--run', str(run),
                                     '--oracle', str(oracle), '--oracle-sha256', digest])

    def execute(command, **kwargs):
        is_oracle = command[1] == str(oracle)
        if is_oracle:
            json.dump({'import_path': str(work / 'src/urllib3/__init__.py'),
                       'results': [{'passed': passed, 'client': 'bare_pool'}]
                                  * oracle_cases}, kwargs['stdout'])
        else:
            kwargs['stdout'].write('upstream test output\n')
            Path(command[command.index('--junitxml') + 1]).write_text(
                f'<testsuites><testsuite tests="{upstream_tests}" skipped="{skipped}" '
                'failures="0" errors="0"/></testsuites>'
            )
        return SimpleNamespace(returncode=oracle_exit if is_oracle else upstream_exit)

    monkeypatch.setattr(evaluator.subprocess, 'run', execute)
    assert evaluator.main() == expected
    assert json.loads((run / 'evaluation/summary.json').read_text())['oracle_exit'] == oracle_exit
    summary = json.loads((run / 'evaluation/summary.json').read_text())
    assert summary['upstream_total'] == upstream_tests
    assert summary['upstream_passed'] == upstream_tests - skipped


def test_graph_runner_exposes_inspection_without_write_tools(tmp_path):
    runner = module('run_codex_agent')
    args = SimpleNamespace(model='example', reasoning='medium', work=tmp_path,
        brain_config=tmp_path/'config', brain_python=tmp_path/'python', brain_src=tmp_path/'src',
        memory_graph=True, memory_search=False)
    command = runner.build_command(args, tmp_path/'out')
    config = dict(value.split('=', 1) for i, value in enumerate(command)
                  if i and command[i-1] == '-c')
    prefix = 'mcp_servers.company-brain.'
    assert json.loads(config[prefix+'enabled_tools']) == runner.READONLY + ['memory_search', 'memory_graph']
    assert json.loads(config[prefix+'disabled_tools']) == ['remember', 'memory_propose']
    assert config[prefix+'tools.memory_graph.approval_mode'] == '"approve"'
    assert config[prefix+'tools.memory_search.approval_mode'] == '"approve"'
