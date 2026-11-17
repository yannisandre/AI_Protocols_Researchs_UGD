"""Hashes of the actual container code, not a claim to capture provider internals."""
import hashlib
import json
from pathlib import Path


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def source_hashes():
    root = Path(__file__).resolve().parent.parent
    paths = list((root / "lab").glob("*.py")) + list((root / "scripts").glob("*.py"))
    if (root / "requirements.lock").exists():
        paths.append(root / "requirements.lock")
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
