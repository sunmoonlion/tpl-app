#!/usr/bin/env python3
"""Verify the Architecture v2 template release lock before instance sync."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "template-release-manifest.json"
IMMUTABLE_IMAGE = re.compile(r"^[^\s]+@sha256:[0-9a-f]{64}$")


class ReleaseError(RuntimeError):
    pass


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    try:
        release = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if release.get("schema_version") != 2:
            raise ReleaseError("template release schema must be 2")
        if release.get("architecture") != "app-platform-v2":
            raise ReleaseError("template release architecture mismatch")
        if release.get("formal_release") is not False:
            raise ReleaseError("R3 template release must remain a candidate")

        source = release["source"]
        source_commit = str(source["commit"])
        if git("rev-parse", f"{source_commit}^{{tree}}") != source["tree"]:
            raise ReleaseError("parent source tree does not match source commit")

        verified: list[str] = []
        for component in release["default_components"]:
            path = str(component["path"])
            commit = str(component["commit"])
            if git("rev-parse", f"{source_commit}:{path}") != commit:
                raise ReleaseError(f"source commit does not lock {path} at {commit}")
            repository = ROOT / path
            if git("rev-parse", "HEAD", cwd=repository) != commit:
                raise ReleaseError(f"working component is not at locked commit: {path}")
            if git("rev-parse", "HEAD^{tree}", cwd=repository) != component["tree"]:
                raise ReleaseError(f"component tree mismatch: {path}")
            file_count = int(git("ls-files", cwd=repository).count("\n") + 1)
            if file_count != component["tracked_files"]:
                raise ReleaseError(f"tracked file count mismatch: {path}")
            if not IMMUTABLE_IMAGE.fullmatch(str(component["image"])):
                raise ReleaseError(f"mutable component image: {path}")
            verified.append(path)

        scaffold = release["kubernetes_scaffold"]
        scaffold_path = str(scaffold["path"])
        if git("rev-parse", f"{source_commit}:{scaffold_path}") != scaffold["tree"]:
            raise ReleaseError("Kubernetes scaffold tree mismatch")
        scaffold_count = len(
            git("ls-tree", "-r", "--name-only", source_commit, scaffold_path).splitlines()
        )
        if scaffold_count != scaffold["tracked_files"]:
            raise ReleaseError("Kubernetes scaffold tracked file count mismatch")

        policy = release["release_policy"]
        if policy.get("r4_sync_order") != ["info", "knowledge", "research"]:
            raise ReleaseError("R4 sync order is not frozen")
        if policy.get("overwrite_v1_1_0_0") is not False:
            raise ReleaseError("v1 1.0.0 protection is not active")

        print(
            json.dumps(
                {
                    "task": "architecture-v2-template-release-lock",
                    "result": "passed",
                    "template_release": release["template_release"],
                    "source_commit": source_commit,
                    "components": verified,
                    "formal_release": False,
                    "credentials_printed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError, KeyError, ReleaseError, subprocess.SubprocessError) as exc:
        print(
            json.dumps(
                {
                    "task": "architecture-v2-template-release-lock",
                    "result": "failed",
                    "error": str(exc),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
