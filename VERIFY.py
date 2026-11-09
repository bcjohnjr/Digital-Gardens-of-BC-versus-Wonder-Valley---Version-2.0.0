#!/usr/bin/env python3
"""Verify the flat research archive against SHA256.txt."""
from pathlib import Path
import hashlib,sys
base=Path(__file__).resolve().parent
ok=0
for line in (base/'SHA256.txt').read_text(encoding='utf-8').splitlines():
    if not line.strip() or line.startswith('#'): continue
    sha,name=line.split('  ',1)
    p=base/name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:
        sys.exit('FAILED: '+name)
    ok+=1
print('PASS:',ok,'files match SHA256.txt')
