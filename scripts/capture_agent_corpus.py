"""Read-only freeze of the eligible urllib3 experiment namespace; never ingest/filter."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from brain.config import load_config
from brain.graph import GraphStore
from brain.services import Services


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    store = GraphStore(load_config(args.config))
    repo = store.cfg.repo_id
    if repo != 'experiment:urllib3:5181:eligible':
        parser.error('this check only supports the already prepared eligible namespace')
    nodes = store.query('MATCH (n {repo_id:$repo}) RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS properties ORDER BY uid', {'repo': repo})
    edges = store.query('MATCH (a {repo_id:$repo})-[r]->(b {repo_id:$repo}) RETURN a.uid AS a, type(r) AS relation, b.uid AS b, properties(r) AS properties ORDER BY a, relation, b', {'repo': repo})
    work = sorted(n['properties']['number'] for n in nodes if set(n['labels']) & {'PR', 'Issue'})
    assert work == [3780, 5161], work
    text_nodes = [n for n in nodes if set(n['labels']) & {'PR', 'Issue', 'Comment', 'Source', 'Document', 'Decision'}]
    blocked = [n['uid'] for n in text_nodes if re.search(r'(?:#|/)(?:5242|5191|5181)\b', json.dumps({k:v for k,v in n['properties'].items() if k in ('excerpt','text','title','body','url')}))]
    assert not blocked, blocked
    payload = {'nodes': nodes, 'edges': edges}
    snapshot = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    responses = {str(n): Services(store).get_context('#' + str(n), scope='org') for n in (3780, 5161, 5242, 5191, 5181)}
    for n in ('3780', '5161'):
        assert responses[n]['status'] in ('ok', 'incomplete') and responses[n]['untrusted_source_excerpts']
    for n in ('5242', '5191', '5181'):
        assert not responses[n]['items']
    result = {'repo_id': repo, 'snapshot_sha256': hashlib.sha256(snapshot).hexdigest(),
              'graph_revision': store.revision(), 'source_ids': sorted(n['uid'] for n in nodes if 'Source' in n['labels']),
              'work_items': work, 'snapshot': payload, 'probe_responses': responses,
              'limitations': ['Read-only observed snapshot; concurrent changes require a post-run comparison.',
                              'Eligible merged history is additional information, not independent discovery.',
                              'Private scope is not used by this preflight.']}
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('snapshot_sha256', 'graph_revision', 'work_items')}))


if __name__ == '__main__':
    main()
