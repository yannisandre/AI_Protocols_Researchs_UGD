"""Read-only checks of this project's Git publication candidates; no network/API calls.

This is a limited release check, not a comprehensive secret scanner. Findings
contain paths and rule names only, never credential values or matched text.
"""
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "provider-key-pattern": re.compile(rb"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}\b"),
    "private-key-material": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "nonempty-env-api-key": re.compile(
        rb"(?m)^[ \t]*(?:LLM_API_KEY|GUARD_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY)[ \t]*=[ \t]*[^\s\r\n]+"),
}
KEY_FIELDS = {"LLM_API_KEY", "GUARD_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"}


def local_api_keys():
    values = set()
    for file in ROOT.glob(".env*"):
        if not file.is_file() or file.name.endswith(".example"):
            continue
        for line in file.read_text().splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() in KEY_FIELDS:
                value = value.strip().strip("\"'")
                if len(value) >= 24 and not value.startswith("${"):
                    values.add(value.encode())
    return values


def private_path(path):
    parts = path.parts
    if any(p in {".local", "tmp", "__pycache__", ".pytest_cache", ".venv"} for p in parts):
        return True
    if parts and parts[0] == "results" and path != Path("results/.gitkeep"):
        return True
    return path.name == "auth.json" or (path.name.startswith(".env") and not path.name.endswith(".example"))


def check():
    raw = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "."], cwd=ROOT)
    candidates = sorted({Path(p.decode()) for p in raw.split(b"\0") if p})
    public = {p.resolve() for p in (ROOT / candidate for candidate in candidates) if p.is_file()}
    secrets = local_api_keys()
    problems, zip_count, total_bytes = [], 0, 0

    def scan(data, label):
        for rule, pattern in PATTERNS.items():
            if pattern.search(data):
                problems.append((label, rule))
        if any(value in data for value in secrets):
            problems.append((label, "exact-local-api-key"))

    for relative in candidates:
        path = ROOT / relative
        if not path.exists():
            # A staged deletion is not content that will be published.
            continue
        if path.is_symlink():
            problems.append((str(relative), "review-symbolic-link"))
            continue
        if not path.is_file():
            continue
        if private_path(relative):
            problems.append((str(relative), "local-file-in-public-candidates"))
            continue
        data = path.read_bytes()
        total_bytes += len(data)
        scan(data, str(relative))
        if path.suffix == ".zip":
            zip_count += 1
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                expanded = 0
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    name = Path(member.filename)
                    label = str(relative) + "::" + member.filename
                    if name.is_absolute() or ".." in name.parts or private_path(name):
                        problems.append((label, "private-or-unsafe-archive-path"))
                        continue
                    expanded += member.file_size
                    if member.file_size > 16_000_000 or expanded > 64_000_000:
                        problems.append((label, "archive-scan-size-limit"))
                        continue
                    scan(archive.read(member), label)
        if path.suffix == ".md":
            text = data.decode("utf-8")
            # Ignore code blocks; shell examples are not Markdown hyperlinks.
            text = re.sub(r"```.*?```", "", text, flags=re.S)
            for target in re.findall(r"!?\[[^\]\n]*\]\(([^)\n]+)\)", text):
                target = target.strip().strip("<>")
                if target.startswith("/") or urlsplit(target).scheme == "file":
                    problems.append((str(relative), "nonportable-absolute-link"))
                    continue
                if urlsplit(target).scheme or target.startswith("#"):
                    continue
                link = path.parent / unquote(target.split("#", 1)[0])
                if not link.exists():
                    problems.append((str(relative), "missing-link-target: " + target))
                elif link.is_file() and link.resolve().is_relative_to(ROOT) and link.resolve() not in public:
                    problems.append((str(relative), "unpublished-link-target: " + target))

    plan = json.loads((ROOT / "experiments/recovery_v2_2026-11-13.json").read_text())
    manifest = json.loads((ROOT / "experiments/evaluation_v2_dataset_manifest.json").read_text())
    frozen = {**plan["source_sha256"],
              **{"fixtures/" + name: value for name, value in plan["fixture_sha256"].items()},
              **manifest["files_sha256"]}
    for name, expected in frozen.items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            problems.append((name, "frozen-runtime-or-corpus-changed"))
    for name, expected in (("recovery-v2-source.zip", "reference/recovery-v2-verification.json"),):
        verification = json.loads((ROOT / expected).read_text())
        if hashlib.sha256((ROOT / "reference" / name).read_bytes()).hexdigest() != verification["source_snapshot_sha256"]:
            problems.append((name, "frozen-source-archive-changed"))

    print(f"Publication candidates: {len(candidates)} files, {total_bytes / 1_000_000:.2f} MB; {zip_count} ZIPs inspected.")
    if problems:
        for path, rule in sorted(set(problems)):
            print(f"FAIL {path}: {rule}")
        print("Publication checks failed. No secret values were printed; no files were changed.")
        return 1
    print(f"PASS: selected secret checks, local file links, {len(frozen)} frozen runtime/corpus hashes and source snapshot.")
    print("No staging, commit, push, provider request or credential change was performed.")
    return 0


if __name__ == "__main__":
    sys.exit(check())
