#!/usr/bin/env python3
"""Validate public lineage. Source integrity and runtime verification are separate."""
from __future__ import annotations
import argparse
import datetime as dt
import re
from pathlib import Path
import yaml

LINEAGE = Path(__file__).resolve().parent / 'lineage.yaml'
STATUSES = {'active', 'archived', 'reference', 'experiment', 'superseded', 'empty'}
LINES = {'substrate', 'surface', 'instrument', 'method', 'world', 'reference'}
TYPES = {'supersedes', 'derives-vocabulary', 'provides-substrate', 'generalizes',
         'instruments', 'demonstrates-method', 'sibling-phase', 'hosts',
         'may-provide-substrate', 'references'}
STATES = {'documented', 'declared', 'inferred', 'unsupported'}
BASIS_STATES = {'repository-reference': {'documented'}, 'owner-report': {'declared'},
                'comparison': {'inferred'}, 'namespace': {'inferred'},
                'role-name': {'inferred'}, 'vocabulary': {'unsupported'}}

class Invalid(ValueError): pass
class UniqueLoader(yaml.SafeLoader): pass

def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise Invalid(f'duplicate or non-string key: {key!r}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result

UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

def load(text):
    try: data = yaml.load(text, Loader=UniqueLoader)
    except yaml.YAMLError as exc: raise Invalid(f'invalid YAML: {exc}') from exc
    errors = validate(data)
    if errors: raise Invalid('\n'.join(errors))
    return data

def nonempty(value):
    return isinstance(value, str) and bool(value.strip())

def valid_date(value):
    try: return dt.date.fromisoformat(str(value)) <= dt.datetime.now(dt.timezone.utc).date()
    except (ValueError, TypeError): return False

def member(value, choices):
    return isinstance(value,str) and value in choices

def digest(value, width):
    return isinstance(value,str) and bool(re.fullmatch('[0-9a-f]{'+str(width)+'}', value))

def safe_path(value):
    return nonempty(value) and not value.startswith('/') and '..' not in Path(value).parts and '\\' not in value

def validate(data):
    errors = []
    def require(ok, message):
        if not ok: errors.append(message)
    if not isinstance(data, dict): return ['root must be a mapping']
    require(data.get('schema') == 'lineage/v1', 'schema must be lineage/v1')
    require(data.get('scope') == 'public', 'scope must be public')
    require(valid_date(data.get('observed')), 'observed must be a non-future ISO date')
    nodes, edges = data.get('nodes'), data.get('edges')
    if not isinstance(nodes, dict) or not nodes: return errors + ['nodes must be a nonempty mapping']
    if not isinstance(edges, list): return errors + ['edges must be a list']
    repos = set()
    for name, node in nodes.items():
        label = f'node {name}'
        require(isinstance(name,str) and bool(re.fullmatch(r'[a-z0-9][a-z0-9-]*', name)), label + ': invalid id')
        if not isinstance(node, dict): errors.append(label + ': must be a mapping'); continue
        repo = node.get('repo', '')
        require(isinstance(repo, str) and bool(re.fullmatch(r'bdf1992/[A-Za-z0-9_.-]+', repo)), label + ': invalid repo')
        require(str(repo).lower() not in repos, label + ': duplicate repo')
        repos.add(str(repo).lower())
        require(node.get('visibility') == 'public', label + ': private repositories cannot be published')
        require(member(node.get('status'), STATUSES), label + ': invalid status')
        require(member(node.get('line'), LINES), label + ': invalid line')
        require(nonempty(node.get('claim')) and len(node.get('claim', '')) <= 350, label + ': invalid claim')
        require(type(node.get('github_archived')) is bool, label + ': github_archived must be Boolean')
        require(type(node.get('fork')) is bool, label + ': fork must be Boolean')
        topics = node.get('topics', '')
        require(isinstance(topics, str), label + ': topics must be a string')
        if isinstance(topics, str):
            require(len(topics.split()) <= 20 and all(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,49}', t) for t in topics.split()), label + ': invalid topics')
        ev = node.get('evidence')
        if not isinstance(ev, dict): errors.append(label + ': evidence must be a mapping'); continue
        require(ev.get('kind') == 'source', label + ': evidence kind must be source')
        for key in ['command', 'result']:
            require(nonempty(ev.get(key)), label + ': missing evidence ' + key)
        require(valid_date(ev.get('observed')), label + ': invalid evidence date')
        for key, width in [('revision',40), ('blob',40), ('sha256',64)]:
            require(digest(ev.get(key),width), label + ': invalid ' + key)
        require(safe_path(ev.get('path')), label + ': unsafe evidence path')
    seen, touched = set(), set()
    for index, edge in enumerate(edges):
        label = f'edge {index}'
        if not isinstance(edge, dict): errors.append(label + ': must be a mapping'); continue
        ends = (edge.get('from'), edge.get('to'))
        require(all(isinstance(end,str) and end in nodes for end in ends), label + ': dangling endpoint')
        require(ends[0] != ends[1], label + ': self relation')
        kind, state = edge.get('type'), edge.get('state')
        require(member(kind,TYPES), label + ': unknown relation type')
        require(member(state,STATES), label + ': unknown evidence state')
        basis = edge.get('basis')
        require(isinstance(basis,str) and basis in BASIS_STATES and state in BASIS_STATES[basis], label + ': basis does not support evidence state')
        key = tuple(map(str, (*ends,kind)))
        require(key not in seen, label + ': duplicate relation'); seen.add(key)
        require(nonempty(edge.get('evidence')), label + ': empty evidence')
        require(nonempty(edge.get('limit')), label + ': missing evidence limit')
        sources = edge.get('sources')
        require(isinstance(sources,list) and bool(sources), label + ': missing sources')
        for source in sources if isinstance(sources,list) else []:
            if not isinstance(source,dict): errors.append(label + ': invalid source'); continue
            require(member(source.get('node'),nodes), label + ': unknown source node')
            require(nonempty(source.get('quote')), label + ': missing source quote')
            require(safe_path(source.get('path')), label + ': unsafe source path')
            for field,width in [('revision',40),('sha256',64)]:
                require(digest(source.get(field),width), label + ': invalid source ' + field)
        if state == 'documented': touched.update(end for end in ends if isinstance(end,str))
    for name, node in nodes.items():
        if isinstance(node,dict) and name not in touched:
            require(nonempty(node.get('unconnected_reason')), f'node {name}: undocumented connectivity needs a reason')
    return errors

def parse(text):
    """Compatibility seam: every projection uses the same validated parser."""
    data = load(text)
    return {name: dict(node, id=name) for name,node in data['nodes'].items()}, data['edges']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', type=Path, default=LINEAGE)
    args = parser.parse_args()
    try: data = load(args.path.read_text())
    except (Invalid,OSError) as exc: print('FAIL:',exc); return 1
    documented = sum(edge['state']=='documented' for edge in data['edges'])
    print(f"PASS: {len(data['nodes'])} public nodes; {documented} documented relations; "
          f"{len(data['edges'])-documented} qualified claims. Runtime suites are not implied.")
    return 0

if __name__ == '__main__': raise SystemExit(main())
