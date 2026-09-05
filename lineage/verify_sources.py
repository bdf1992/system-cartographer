#!/usr/bin/env python3
"""Read pinned public source bytes; never execute commands stored in the lineage."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import urllib.request
from functools import lru_cache
from pathlib import Path
from validate import LINEAGE, load

def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'lineage-source-check'})
    with urllib.request.urlopen(request,timeout=30) as response: return response.read()

@lru_cache(maxsize=128)
def read_source(repo,revision,path,root,remote):
    if remote:
        return fetch(f'https://raw.githubusercontent.com/{repo}/{revision}/{path}')
    local=Path(root)/repo.split('/')[1]
    return subprocess.check_output(['git','show',f'{revision}:{path}'],cwd=local,stderr=subprocess.PIPE)

def check_source(repo,source,root,remote):
    raw=read_source(repo,source['revision'],source['path'],str(root),remote)
    actual=hashlib.sha256(raw).hexdigest()
    if actual!=source['sha256']: raise ValueError(f'{repo}:{source["path"]}: SHA256 mismatch')
    if 'blob' in source:
        blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if blob!=source['blob']: raise ValueError(f'{repo}: Git blob mismatch')
    if 'quote' in source and source['quote'] not in raw.decode('utf-8'):
        raise ValueError(f'{repo}:{source["path"]}: evidence quote absent')
    return actual

def verify_node(data,name,root,remote):
    node=data['nodes'][name]
    check_source(node['repo'],node['evidence'],root,remote)
    for edge in data['edges']:
        for source in edge['sources']:
            if source['node']==name: check_source(node['repo'],source,root,remote)
    return name

def verify_inventory(data,live=False):
    if live:
        repos=[]; page=1
        while True:
            batch=json.loads(fetch(f'https://api.github.com/users/bdf1992/repos?type=owner&per_page=100&page={page}'))
            if not isinstance(batch,list): raise ValueError('inventory API did not return a list')
            repos.extend({'repo':r['full_name'],'visibility':r['visibility'],'archived':r['archived'],'fork':r['fork']} for r in batch)
            if len(batch)<100: break
            page+=1
    else: repos=json.loads((LINEAGE.parent/'public-inventory.json').read_text())['repositories']
    actual={r['repo'].lower():r for r in repos if r['visibility']=='public'}
    declared={n['repo'].lower():n for n in data['nodes'].values()}
    if actual.keys()!=declared.keys():
        raise ValueError(f'public inventory mismatch; missing={sorted(actual.keys()-declared.keys())}; extra={sorted(declared.keys()-actual.keys())}')
    for key,node in declared.items():
        for field,sourcefield in [('github_archived','archived'),('fork','fork')]:
            if node[field]!=actual[key][sourcefield]:raise ValueError(f'{key}: {field} drift')
    return len(actual)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote',action='store_true')
    parser.add_argument('--repos',type=Path,default=LINEAGE.parents[2])
    parser.add_argument('--node')
    parser.add_argument('--live-inventory',action='store_true')
    args=parser.parse_args(); data=load(LINEAGE.read_text())
    try:
        if not args.node: verify_inventory(data,args.live_inventory)
        names=[args.node] if args.node else list(data['nodes'])
        if any(name not in data['nodes'] for name in names): raise ValueError('unknown node')
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(lambda n:verify_node(data,n,args.repos,args.remote),names))
        for name in results: print(f'PASS {name}: pinned source hashes and cited quotes verified')
        return 0
    except Exception as exc:
        print(f'FAIL: {exc}'); return 1
if __name__=='__main__': raise SystemExit(main())
