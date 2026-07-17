#!/usr/bin/env python3
"""Mirror Theo's fflags dumps into AE12IA/offsets version branches."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "https://offsets.imtheo.lol"
RAW_GITHUB = "https://raw.githubusercontent.com/AE12IA/offsets"
USER_AGENT = "AE12IA-offsets-mirror/1.0 (github.com/AE12IA/offsets)"


def repo_root() -> str:
    env = os.environ.get("GITHUB_WORKSPACE")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def run(
    args: list[str],
    *,
    cwd: str | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        args,
        cwd=cwd or repo_root(),
        check=check,
        text=True,
        capture_output=True,
        env=merged,
    )


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def fetch_versions() -> list[dict[str, Any]]:
    data = json.loads(http_get(f"{BASE_URL}/versions").decode("utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Unexpected versions payload")
    return data


def files_available_names(entry: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for item in entry.get("files_available") or []:
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict) and item.get("name"):
            names.add(str(item["name"]))
    return names


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def remote_branch_exists(version: str) -> bool:
    proc = run(["git", "ls-remote", "--heads", "origin", version], check=False)
    return bool(proc.stdout.strip())


def remote_file_sha256(version: str, filename: str) -> str | None:
    url = f"{RAW_GITHUB}/{version}/{filename}"
    try:
        return sha256_bytes(http_get(url))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def download_fflags(version: str) -> tuple[bytes | None, bytes | None]:
    hpp_url = f"{BASE_URL}/{version}/fflags.hpp"
    try:
        hpp = http_get(hpp_url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, None
        raise

    json_bytes: bytes | None = None
    json_url = f"{BASE_URL}/{version}/fflags.json"
    try:
        json_bytes = http_get(json_url)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    return hpp, json_bytes


def git_identity_env() -> dict[str, str]:
    name = os.environ.get("GIT_AUTHOR_NAME", "AE12IA")
    email = os.environ.get("GIT_AUTHOR_EMAIL", "ae12ia@users.noreply.github.com")
    return {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": os.environ.get("GIT_COMMITTER_NAME", name),
        "GIT_COMMITTER_EMAIL": os.environ.get("GIT_COMMITTER_EMAIL", email),
    }


def prepare_branch(version: str) -> None:
    root = repo_root()
    run(["git", "fetch", "origin", "main"], cwd=root, check=False)
    if remote_branch_exists(version):
        run(["git", "fetch", "origin", version], cwd=root, check=False)
        run(["git", "checkout", version], cwd=root)
        proc = run(["git", "rev-parse", f"origin/{version}"], cwd=root, check=False)
        if proc.returncode == 0 and proc.stdout.strip():
            run(["git", "reset", "--hard", f"origin/{version}"], cwd=root)
    else:
        run(["git", "checkout", "main"], cwd=root)
        run(["git", "pull", "--ff-only", "origin", "main"], cwd=root, check=False)
        run(["git", "checkout", "-B", version], cwd=root)


def write_mirror_files(hpp: bytes, json_bytes: bytes | None) -> list[str]:
    root = repo_root()
    changed: list[str] = []
    hpp_path = os.path.join(root, "offsets.hpp")
    if not os.path.exists(hpp_path) or open(hpp_path, "rb").read() != hpp:
        with open(hpp_path, "wb") as fh:
            fh.write(hpp)
        changed.append("offsets.hpp")

    if json_bytes is not None:
        json_path = os.path.join(root, "offsets.json")
        if not os.path.exists(json_path) or open(json_path, "rb").read() != json_bytes:
            with open(json_path, "wb") as fh:
                fh.write(json_bytes)
            changed.append("offsets.json")
    return changed


def commit_and_push(version: str, changed: list[str]) -> bool:
    root = repo_root()
    run(["git", "add", *changed], cwd=root)
    diff = run(["git", "diff", "--cached", "--quiet"], cwd=root, check=False)
    if diff.returncode == 0:
        return False
    msg = f"Mirror fflags.hpp from offsets.imtheo.lol as offsets.hpp for {version}"
    run(["git", "commit", "-m", msg], cwd=root, env=git_identity_env())
    run(["git", "push", "origin", version], cwd=root)
    return True


def needs_update(version: str, hpp: bytes, json_bytes: bytes | None) -> bool:
    if not remote_branch_exists(version):
        return True
    remote_hpp = remote_file_sha256(version, "offsets.hpp")
    if remote_hpp != sha256_bytes(hpp):
        return True
    if json_bytes is not None:
        remote_json = remote_file_sha256(version, "offsets.json")
        if remote_json != sha256_bytes(json_bytes):
            return True
    return False


def iter_candidates(versions: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for entry in versions:
        version = entry.get("version") or ""
        if not version.startswith("version-"):
            continue
        if "fflags.hpp" not in files_available_names(entry):
            continue
        out.append(version)
    return out


def remote_version_branches() -> set[str]:
    proc = run(["git", "ls-remote", "--heads", "origin"], check=False)
    out: set[str] = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        if ref.startswith("refs/heads/version-"):
            out.add(ref[len("refs/heads/") :])
    return out


def parse_iso_ts(iso: str) -> float:
    if not iso:
        return 0.0
    try:
        from datetime import datetime

        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def build_versions_index(theo_versions: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Public index for the Leviathan site picker (version + publish date)."""
    present = remote_version_branches()
    index: list[dict[str, str]] = []
    for entry in theo_versions:
        version = str(entry.get("version") or "")
        if version not in present:
            continue
        if "fflags.hpp" not in files_available_names(entry):
            continue
        date = str(
            entry.get("last_updated")
            or entry.get("created_at")
            or entry.get("updated_at")
            or ""
        )
        index.append({"version": version, "date": date})

    index.sort(
        key=lambda item: (parse_iso_ts(item["date"]), item["version"]),
        reverse=True,
    )
    return index


def update_versions_json(theo_versions: list[dict[str, Any]], dry_run: bool = False) -> bool:
    root = repo_root()
    run(["git", "checkout", "main"], cwd=root, check=False)
    run(["git", "pull", "--ff-only", "origin", "main"], cwd=root, check=False)

    index = build_versions_index(theo_versions)
    payload = (json.dumps(index, indent=2) + "\n").encode("utf-8")
    path = os.path.join(root, "versions.json")

    if os.path.exists(path) and open(path, "rb").read() == payload:
        print("versions.json: unchanged")
        return False

    if dry_run:
        print(f"versions.json: would_update ({len(index)} entries)")
        return False

    with open(path, "wb") as fh:
        fh.write(payload)

    run(["git", "add", "versions.json"], cwd=root)
    diff = run(["git", "diff", "--cached", "--quiet"], cwd=root, check=False)
    if diff.returncode == 0:
        return False

    run(
        [
            "git",
            "commit",
            "-m",
            f"Update versions.json ({len(index)} mirrored versions)",
        ],
        cwd=root,
        env=git_identity_env(),
    )
    run(["git", "push", "origin", "main"], cwd=root)
    print(f"versions.json: updated ({len(index)} entries)")
    return True


def sync_version(version: str, dry_run: bool = False) -> str:
    hpp, json_bytes = download_fflags(version)
    if hpp is None:
        return "skip_404"

    if not needs_update(version, hpp, json_bytes):
        return "skip_unchanged"

    if dry_run:
        return "would_update"

    prepare_branch(version)
    changed = write_mirror_files(hpp, json_bytes)
    if not changed:
        run(["git", "checkout", "main"], cwd=repo_root(), check=False)
        return "skip_unchanged"

    pushed = commit_and_push(version, changed)
    run(["git", "checkout", "main"], cwd=repo_root(), check=False)
    return "updated" if pushed else "skip_unchanged"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--versions", nargs="*")
    args = parser.parse_args()

    os.chdir(repo_root())
    run(["git", "checkout", "main"], check=False)
    versions = fetch_versions()
    candidates = iter_candidates(versions)
    if args.versions:
        wanted = set(args.versions)
        candidates = [v for v in candidates if v in wanted]

    results: dict[str, list[str]] = {
        "updated": [],
        "skip_unchanged": [],
        "skip_404": [],
        "would_update": [],
    }

    for version in candidates:
        status = sync_version(version, dry_run=args.dry_run)
        results[status].append(version)
        print(f"{version}: {status}")

    update_versions_json(versions, dry_run=args.dry_run)

    print(json.dumps({k: len(v) for k, v in results.items()}, indent=2))
    if results["updated"]:
        print("updated:", ", ".join(results["updated"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())