#!/usr/bin/env python3
"""Apply or clean one rendered Architecture v2 Kubernetes bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import yaml


class DeployError(RuntimeError):
    pass


def run(
    command: list[str],
    *,
    input_bytes: bytes | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env.pop("DEBUG", None)
    return subprocess.run(
        command,
        input=input_bytes,
        check=True,
        capture_output=capture,
        env=env,
    )


def kubectl(args: argparse.Namespace, *items: str, **kwargs):
    command = [args.kubectl]
    if args.kubeconfig:
        command.extend(("--kubeconfig", str(args.kubeconfig)))
    command.extend(items)
    return run(command, **kwargs)


def load_bundle(path: Path) -> dict[str, object]:
    release_file = path / "release.json"
    if not release_file.is_file():
        raise DeployError(f"missing release.json in {path}")
    release = json.loads(release_file.read_text(encoding="utf-8"))
    if release.get("schema_version") != 1 or release.get("architecture") != "app-platform-v2":
        raise DeployError("unsupported bundle schema/architecture")
    hashes = release.get("sha256")
    if not isinstance(hashes, dict):
        raise DeployError("bundle does not contain file hashes")
    for name, expected in hashes.items():
        resource = path / str(name)
        actual = hashlib.sha256(resource.read_bytes()).hexdigest()
        if actual != expected:
            raise DeployError(f"bundle hash mismatch: {name}")
    return release


def parse_secret(path: Path, required: set[str], optional: set[str]) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise DeployError("secret env file must not be accessible by group/other")
    found: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped or stripped.startswith("export "):
            raise DeployError(f"invalid secret env syntax at line {number}")
        key, value = stripped.split("=", 1)
        if key in found or key not in required | optional or not value:
            raise DeployError(f"invalid, duplicate or empty secret key at line {number}")
        found.add(key)
    if not required <= found:
        raise DeployError(f"secret key mismatch missing={sorted(required-found)}")


def apply_file(args: argparse.Namespace, bundle: Path, name: str) -> None:
    kubectl(args, "apply", "-f", str(bundle / name))


def apply_runtime_component(
    args: argparse.Namespace, bundle: Path, resource_name: str
) -> None:
    documents = [
        item
        for item in yaml.safe_load_all(
            (bundle / "20-runtime.yaml").read_text(encoding="utf-8")
        )
        if item and item.get("metadata", {}).get("name") == resource_name
    ]
    if not any(item.get("kind") == "Deployment" for item in documents):
        raise DeployError(f"runtime component is missing Deployment/{resource_name}")
    payload = yaml.safe_dump_all(
        documents, sort_keys=False, allow_unicode=True
    ).encode("utf-8")
    kubectl(args, "apply", "-f", "-", input_bytes=payload)


def run_migration(
    args: argparse.Namespace,
    bundle: Path,
    *,
    namespace: str,
    app: str,
    release_id: str,
) -> None:
    migration = f"{app}-backend-migration-{release_id}"
    kubectl(
        args,
        "delete",
        "job",
        migration,
        "-n",
        namespace,
        "--ignore-not-found=true",
        "--wait=true",
    )
    apply_file(args, bundle, "10-migration.yaml")
    try:
        kubectl(
            args,
            "wait",
            "--for=condition=complete",
            f"job/{migration}",
            "-n",
            namespace,
            f"--timeout={args.timeout}s",
        )
    except subprocess.CalledProcessError:
        log_command = [args.kubectl]
        if args.kubeconfig:
            log_command.extend(("--kubeconfig", str(args.kubeconfig)))
        log_command.extend(
            ("logs", f"job/{migration}", "-n", namespace, "--tail=100")
        )
        subprocess.run(log_command, check=False)
        raise
    kubectl(args, "logs", f"job/{migration}", "-n", namespace, "--tail=100")
    kubectl(args, "delete", "job", migration, "-n", namespace, "--wait=true")


def apply(args: argparse.Namespace, bundle: Path, release: dict[str, object]) -> None:
    namespace = str(release["namespace"])
    app = str(release["app"])
    release_id = str(release["release_id"])
    secret_name = str(release["secret_name"])
    secret_file = args.secret_env_file.resolve()
    parse_secret(
        secret_file,
        set(release["secret_keys"]),
        set(release.get("optional_secret_keys", [])),
    )

    apply_file(args, bundle, "00-prerequisites.yaml")
    dependencies = release.get("dependencies")
    if not isinstance(dependencies, dict):
        raise DeployError("bundle does not declare external Secret dependencies")
    for name in (
        str(dependencies["image_pull_secret"]),
        str(dependencies["tls_secret"]),
    ):
        kubectl(args, "get", "secret", name, "-n", namespace, capture=True)

    secret_yaml = kubectl(
        args,
        "create",
        "secret",
        "generic",
        secret_name,
        "-n",
        namespace,
        f"--from-env-file={secret_file}",
        "--dry-run=client",
        "-o",
        "yaml",
        capture=True,
    ).stdout
    kubectl(args, "apply", "-f", "-", input_bytes=secret_yaml)
    kubectl(
        args,
        "label",
        "secret",
        secret_name,
        "-n",
        namespace,
        f"sunmoonai.com/app={app}",
        "sunmoonai.com/managed-by=architecture-v2",
        "--overwrite",
        capture=True,
    )

    apply_file(args, bundle, "30-network-policies.yaml")

    if args.component == "prerequisites":
        print(json.dumps({"result": "passed", "component": args.component}))
        return
    if args.component == "network-policies":
        print(json.dumps({"result": "passed", "component": args.component}))
        return
    if args.component == "ingress":
        apply_file(args, bundle, "40-ingress.yaml")
        print(json.dumps({"result": "passed", "component": args.component}))
        return
    if args.component == "migration":
        run_migration(
            args,
            bundle,
            namespace=namespace,
            app=app,
            release_id=release_id,
        )
        print(json.dumps({"result": "passed", "component": args.component}))
        return
    if args.component != "all":
        resource_name = f"{app}-{args.component}"
        apply_runtime_component(args, bundle, resource_name)
        if args.component in {"backend-api", "admin-frontend", "web-frontend"}:
            apply_file(args, bundle, "40-ingress.yaml")
        kubectl(
            args,
            "rollout",
            "status",
            f"deployment/{resource_name}",
            "-n",
            namespace,
            f"--timeout={args.timeout}s",
        )
        print(
            json.dumps(
                {"result": "passed", "component": args.component, "deployment": resource_name}
            )
        )
        return

    run_migration(
        args,
        bundle,
        namespace=namespace,
        app=app,
        release_id=release_id,
    )

    apply_file(args, bundle, "20-runtime.yaml")
    apply_file(args, bundle, "40-ingress.yaml")
    deployments = (
        f"{app}-backend-api",
        f"{app}-backend-worker",
        f"{app}-backend-scheduler",
        f"{app}-admin-frontend",
        f"{app}-web-frontend",
    )
    for deployment in deployments:
        kubectl(
            args,
            "rollout",
            "status",
            f"deployment/{deployment}",
            "-n",
            namespace,
            f"--timeout={args.timeout}s",
        )
    print(
        json.dumps(
            {
                "task": "app-platform-deploy",
                "result": "passed",
                "app": app,
                "namespace": namespace,
                "release_id": release_id,
                "migration_job_cleaned": True,
                "credentials_printed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cleanup(args: argparse.Namespace, release: dict[str, object]) -> None:
    namespace = str(release["namespace"])
    app = str(release["app"])
    selector = f"sunmoonai.com/managed-by=architecture-v2,sunmoonai.com/app={app}"
    kinds = (
        "ingressroute,networkpolicy,horizontalpodautoscaler,poddisruptionbudget,"
        "deployment,service,configmap,serviceaccount,job,secret"
    )
    kubectl(
        args,
        "delete",
        kinds,
        "-n",
        namespace,
        "-l",
        selector,
        "--ignore-not-found=true",
        "--wait=true",
    )
    if args.delete_namespace:
        kubectl(
            args,
            "delete",
            "namespace",
            namespace,
            "--ignore-not-found=true",
            "--wait=true",
        )
    print(json.dumps({"result": "cleaned", "app": app, "namespace": namespace}))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "apply", "cleanup"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--secret-env-file", type=Path)
    parser.add_argument("--kubeconfig", type=Path)
    parser.add_argument("--kubectl", default="kubectl")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--component",
        choices=(
            "all",
            "prerequisites",
            "migration",
            "network-policies",
            "backend-api",
            "backend-worker",
            "backend-scheduler",
            "admin-frontend",
            "web-frontend",
            "ingress",
        ),
        default="all",
    )
    parser.add_argument("--delete-namespace", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = args.bundle.resolve()
    try:
        release = load_bundle(bundle)
        if args.action == "plan":
            print(json.dumps({"result": "valid", **release}, ensure_ascii=False, indent=2))
        elif args.action == "apply":
            if args.secret_env_file is None:
                raise DeployError("apply requires --secret-env-file")
            apply(args, bundle, release)
        else:
            cleanup(args, release)
        return 0
    except (DeployError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(
            json.dumps({"result": "failed", "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
