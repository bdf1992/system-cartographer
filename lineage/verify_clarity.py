#!/usr/bin/env python3
"""Check recorded prose and source digests; this does not perform editorial review."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(path):return 'sha256:'+hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
def main():
    data=json.loads((ROOT/'.clarity/coverage.json').read_text());errors=[]
    if data.get('schema')!='soveraeign-clarity-coverage/v1' or data.get('skill')!='clarity/v1':errors.append('invalid receipt schema')
    for path,review in data.get('reviews',{}).items():
        try:
            if digest(path)!=review['artifact_digest']:errors.append(path+': TEXT_STALE')
            for basis in review['basis']:
                if digest(basis['path'])!=basis['digest']:errors.append(path+': BASIS_STALE '+basis['path'])
        except (OSError,KeyError):errors.append(path+': missing artifact or basis')
    if errors:print('\n'.join(errors));return 1
    print(f"PASS: {len(data['reviews'])} prose review receipts current");return 0
if __name__=='__main__':raise SystemExit(main())
