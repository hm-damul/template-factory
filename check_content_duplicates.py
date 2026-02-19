
import os
import json
from pathlib import Path
import hashlib

def get_dir_hash(directory):
    """간단한 디렉토리 콘텐츠 해시 (디자인/내용 중복 체크용)"""
    hasher = hashlib.md5()
    # 주요 파일들만 체크: index.html (디자인), product_en.md (내용)
    targets = ["index.html", "product_en.md"]
    for target in targets:
        p = Path(directory) / target
        if p.exists():
            hasher.update(p.read_bytes())
    return hasher.hexdigest()

outputs_dir = Path("outputs")
hashes = {}
duplicates = []

if outputs_dir.exists():
    for d in outputs_dir.iterdir():
        if d.is_dir():
            h = get_dir_hash(d)
            if h in hashes:
                duplicates.append((d.name, hashes[h]))
            else:
                hashes[h] = d.name

if duplicates:
    print(f"Found {len(duplicates)} potential duplicates (same design/content):")
    for dup, original in duplicates:
        print(f" - {dup} (matches {original})")
else:
    print("No exact design/content duplicates found in outputs.")
