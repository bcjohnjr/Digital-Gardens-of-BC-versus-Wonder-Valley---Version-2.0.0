#!/usr/bin/env python3
"""OPTIONAL: Rebuild a shorter, runnable research tree from a FLAT archive.

This command does not alter or delete the original extracted flat files.
It creates J/, R/, P/, V/, ROOT/ relative to this script.
"""
from pathlib import Path
import csv,hashlib,shutil,sys
base=Path(__file__).resolve().parent
idx=base/'FILE_INDEX.csv'
if not idx.exists():
    sys.exit('FILE_INDEX.csv not found alongside RESTORE.py')
count=0
for row in csv.DictReader(idx.open(newline='',encoding='utf-8-sig')):
    src=(base/row['file']).resolve()
    out=(base/row['restored_path']).resolve()
    if src.parent!=base or base not in out.parents:
        sys.exit('Unsafe mapping in FILE_INDEX.csv')
    if not src.is_file():
        sys.exit('Missing file: '+row['file'])
    if hashlib.sha256(src.read_bytes()).hexdigest()!=row['sha256']:
        sys.exit('Checksum mismatch: '+row['file'])
    out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(src,out)
    count+=1
print('Restored',count,'unchanged original files into J/, R/, P/, V/, ROOT/.')
print('To run unit tests: python R/02_PRIVATE_RESEARCH/code/test_model.py')
