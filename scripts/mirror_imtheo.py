#!/usr/bin/env python3
"""Mirror Theo dumps into AE12IA/offsets on a single branch: fflag_offset.

Layout (cuts off old fflag clients that still hit version-*/offsets.hpp):
  branch fflag_offset/
    versions.json
    prefixes.json      (seeded from main, left alone unless present)
    build_map.json     (seeded from main)
    version-<hash>/
      offsets.hpp
      offsets.json     (optional)

Theo source stays offsets.imtheo.lol. Old main + version-* branches are frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "https://offsets.imtheo.lol"
RAW_GITHUB = "https://raw.githubusercontent.com/AE12IA/offsets"
INDEX_BRANCH = "fflag_offset"
USER_AGENT = "AE12IA-offsets-mirror/1.1 (github.com/AE12IA/offsets; fflag_offset)"


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


def git_identity_env() -> dict[str, str]:
    name = os.environ.get("GIT_AUTHOR_NAME", "AE12IA")
    email = os.environ.get("GIT_AUTHOR_EMAIL", "ae12ia@users.noreply.github.com")
    return {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": os.environ.get("GIT_COMMITTER_NAME", name),
        "GIT_COMMITTER_EMAIL": os.environ.get("GIT_COMMITTER_EMAIL", email),
    }


def remote_branch_exists(branch: str) -> bool:
    proc = run(["git", "ls-remote", "--heads", "origin", branch], check=False)
    return bool(proc.stdout.strip())


def remote_file_sha256(relpath: str) -> str | None:
    url = f"{RAW_GITHUB}/{INDEX_BRANCH}/{relpath}"
    try:
        return sha256_bytes(http_get(url))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def download_file_pair(version: str, hpp_name: str, json_name: str) -> tuple[bytes | None, bytes | None]:
    try:
        hpp = http_get(f"{BASE_URL}/{version}/{hpp_name}")
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):
            return None, None
        raise

    json_bytes: bytes | None = None
    try:
        json_bytes = http_get(f"{BASE_URL}/{version}/{json_name}")
    except urllib.error.HTTPError as exc:
        if exc.code not in (403, 404):
            raise
    return hpp, json_bytes


def download_fflags(version: str) -> tuple[bytes | None, bytes | None]:
    return download_file_pair(version, "fflags.hpp", "fflags.json")


def download_offsets(version: str) -> tuple[bytes | None, bytes | None]:
    return download_file_pair(version, "offsets.hpp", "offsets.json")


def ensure_index_branch() -> None:
    """Checkout fflag_offset, creating it from main on first run."""
    root = repo_root()
    run(["git", "fetch", "origin"], cwd=root, check=False)

    if remote_branch_exists(INDEX_BRANCH):
        run(["git", "fetch", "origin", INDEX_BRANCH], cwd=root, check=False)
        run(["git", "checkout", INDEX_BRANCH], cwd=root)
        proc = run(["git", "rev-parse", f"origin/{INDEX_BRANCH}"], cwd=root, check=False)
        if proc.returncode == 0 and proc.stdout.strip():
            run(["git", "reset", "--hard", f"origin/{INDEX_BRANCH}"], cwd=root)
        return

    # First-time seed from main (keeps prefixes.json / build_map.json if present)
    run(["git", "fetch", "origin", "main"], cwd=root, check=False)
    run(["git", "checkout", "main"], cwd=root, check=False)
    run(["git", "pull", "--ff-only", "origin", "main"], cwd=root, check=False)
    run(["git", "checkout", "-B", INDEX_BRANCH], cwd=root)
    print(f"{INDEX_BRANCH}: created from main")


def write_version_files(version: str, hpp: bytes, json_bytes: bytes | None) -> list[str]:
    root = repo_root()
    folder = os.path.join(root, version)
    os.makedirs(folder, exist_ok=True)
    changed: list[str] = []

    hpp_path = os.path.join(folder, "offsets.hpp")
    if not os.path.exists(hpp_path) or open(hpp_path, "rb").read() != hpp:
        with open(hpp_path, "wb") as fh:
            fh.write(hpp)
        changed.append(f"{version}/offsets.hpp")

    if json_bytes is not None:
        json_path = os.path.join(folder, "offsets.json")
        if not os.path.exists(json_path) or open(json_path, "rb").read() != json_bytes:
            with open(json_path, "wb") as fh:
                fh.write(json_bytes)
            changed.append(f"{version}/offsets.json")
    return changed


def needs_update(version: str, hpp: bytes, json_bytes: bytes | None) -> bool:
    remote_hpp = remote_file_sha256(f"{version}/offsets.hpp")
    if remote_hpp != sha256_bytes(hpp):
        return True
    if json_bytes is not None:
        remote_json = remote_file_sha256(f"{version}/offsets.json")
        if remote_json != sha256_bytes(json_bytes):
            return True
    return False


def commit_and_push(changed: list[str], message: str) -> bool:
    root = repo_root()
    run(["git", "add", "--", *changed], cwd=root)
    diff = run(["git", "diff", "--cached", "--quiet"], cwd=root, check=False)
    if diff.returncode == 0:
        return False
    run(["git", "commit", "-m", message], cwd=root, env=git_identity_env())
    run(["git", "push", "-u", "origin", INDEX_BRANCH], cwd=root)
    return True


def iter_candidates(versions: list[dict[str, Any]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for entry in versions:
        version = entry.get("version") or ""
        if not version.startswith("version-"):
            continue
        names = files_available_names(entry)
        if "fflags.hpp" in names:
            out.append((version, "fflags"))
        elif "offsets.hpp" in names:
            out.append((version, "offsets"))
    return out


def normalize_file_version(raw: str) -> str:
    parts = [p.strip() for p in re.split(r"[,\s]+", raw.strip()) if p.strip()]
    if len(parts) < 4:
        return ""
    return ".".join(parts[:4])


def fetch_deploy_history_map() -> dict[str, str]:
    try:
        text = http_get("https://setup.rbxcdn.com/DeployHistory.txt").decode(
            "utf-8", errors="replace"
        )
    except Exception as exc:
        print(f"DeployHistory: skipped ({exc})")
        return {}

    out: dict[str, str] = {}
    pattern = re.compile(
        r"WindowsPlayer\s+(version-[0-9a-fA-F]+)\s+at.*?file version:\s*([0-9,\s]+)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        version = match.group(1)
        client = normalize_file_version(match.group(2))
        if client and version not in out:
            out[version] = client
    return out


def fetch_build_map() -> dict[str, str]:
    try:
        data = json.loads(
            http_get(f"{RAW_GITHUB}/{INDEX_BRANCH}/build_map.json").decode("utf-8")
        )
    except Exception:
        try:
            data = json.loads(http_get(f"{RAW_GITHUB}/main/build_map.json").decode("utf-8"))
        except Exception:
            return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if v}


def local_mirrored_versions() -> set[str]:
    root = repo_root()
    out: set[str] = set()
    try:
        for name in os.listdir(root):
            if name.startswith("version-") and os.path.isdir(os.path.join(root, name)):
                if os.path.isfile(os.path.join(root, name, "offsets.hpp")):
                    out.add(name)
    except FileNotFoundError:
        pass
    return out


def client_label_for_version(
    version: str,
    deploy_map: dict[str, str],
    build_map: dict[str, str],
) -> str:
    if version in deploy_map:
        return deploy_map[version]
    for client, mapped in build_map.items():
        if mapped == version:
            return client
    return ""


def parse_iso_ts(iso: str) -> float:
    if not iso:
        return 0.0
    try:
        from datetime import datetime

        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def build_versions_index(theo_versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    present = local_mirrored_versions()
    deploy_map = fetch_deploy_history_map()
    build_map = fetch_build_map()
    theo_by_version = {
        str(entry.get("version") or ""): entry for entry in theo_versions if entry.get("version")
    }

    index: list[dict[str, Any]] = []
    for version in sorted(present):
        entry = theo_by_version.get(version, {})
        names = files_available_names(entry) if entry else set()
        has_fflags = "fflags.hpp" in names if names else True
        date = str(
            entry.get("last_updated")
            or entry.get("created_at")
            or entry.get("updated_at")
            or ""
        )
        item: dict[str, Any] = {
            "version": version,
            "date": date,
            "has_fflags": has_fflags,
        }
        client = client_label_for_version(version, deploy_map, build_map)
        if client:
            item["client"] = client
        index.append(item)

    index.sort(
        key=lambda item: (parse_iso_ts(str(item.get("date") or "")), str(item["version"])),
        reverse=True,
    )
    return index


def write_versions_json(theo_versions: list[dict[str, Any]], dry_run: bool = False) -> list[str]:
    index = build_versions_index(theo_versions)
    payload = (json.dumps(index, indent=2) + "\n").encode("utf-8")
    path = os.path.join(repo_root(), "versions.json")

    if os.path.exists(path) and open(path, "rb").read() == payload:
        print("versions.json: unchanged")
        return []

    if dry_run:
        print(f"versions.json: would_update ({len(index)} entries)")
        return []

    with open(path, "wb") as fh:
        fh.write(payload)
    print(f"versions.json: staged ({len(index)} entries)")
    return ["versions.json"]


def sync_version(version: str, source: str, dry_run: bool = False) -> tuple[str, list[str]]:
    if source == "fflags":
        hpp, json_bytes = download_fflags(version)
    else:
        hpp, json_bytes = download_offsets(version)
    if hpp is None:
        return "skip_404", []

    if not needs_update(version, hpp, json_bytes):
        return "skip_unchanged", []

    if dry_run:
        return "would_update", []

    changed = write_version_files(version, hpp, json_bytes)
    if not changed:
        return "skip_unchanged", []
    return "updated", changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--versions", nargs="*")
    args = parser.parse_args()

    os.chdir(repo_root())
    if not args.dry_run:
        ensure_index_branch()
    else:
        run(["git", "fetch", "origin"], check=False)

    versions = fetch_versions()
    candidates = iter_candidates(versions)
    if args.versions:
        wanted = set(args.versions)
        candidates = [(v, s) for v, s in candidates if v in wanted]

    results: dict[str, list[str]] = {
        "updated": [],
        "skip_unchanged": [],
        "skip_404": [],
        "would_update": [],
    }
    pending: list[str] = []
    messages: list[str] = []

    for version, source in candidates:
        status, changed = sync_version(version, source, dry_run=args.dry_run)
        results[status].append(version)
        print(f"{version} ({source}): {status}")
        if changed:
            pending.extend(changed)
            label = "fflags.hpp" if source == "fflags" else "offsets.hpp"
            messages.append(f"Mirror {label} → {INDEX_BRANCH}/{version}/offsets.hpp")

    pending.extend(write_versions_json(versions, dry_run=args.dry_run))

    if pending and not args.dry_run:
        msg = messages[0] if len(messages) == 1 else (
            f"Mirror Theo dumps on {INDEX_BRANCH} ({len(results['updated'])} versions)"
        )
        if "versions.json" in pending and not messages:
            msg = f"Update versions.json on {INDEX_BRANCH}"
        pushed = commit_and_push(pending, msg)
        print(f"push {INDEX_BRANCH}: {'ok' if pushed else 'nothing'}")

    print(json.dumps({k: len(v) for k, v in results.items()}, indent=2))
    if results["updated"]:
        print("updated:", ", ".join(results["updated"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
