#!/usr/bin/env python3
"""Render an immutable Architecture v2 App Kubernetes bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "templates"
FILES = (
    "00-prerequisites.yaml",
    "10-migration.yaml",
    "20-runtime.yaml",
    "30-network-policies.yaml",
    "40-ingress.yaml",
)
IMMUTABLE_IMAGE = re.compile(r"^[^\s]+@sha256:[0-9a-f]{64}$")
DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
LABEL_KEY = re.compile(
    r"^(?:[a-z0-9](?:[-a-z0-9.]{0,251}[a-z0-9])?/)?"
    r"[A-Za-z0-9](?:[-A-Za-z0-9_.]{0,61}[A-Za-z0-9])?$"
)
TOKEN = re.compile(r"__[A-Z0-9_]+__")


def dns_label(value: str, *, field: str, max_length: int = 63) -> str:
    if len(value) > max_length or not DNS_LABEL.fullmatch(value):
        raise ValueError(f"{field} must be a DNS label no longer than {max_length}")
    return value


def immutable_image(value: str, *, field: str) -> str:
    if not IMMUTABLE_IMAGE.fullmatch(value):
        raise ValueError(f"{field} must use repository@sha256:<64 lowercase hex>")
    return value


def strict_origin(value: str, *, field: str, https: bool = True) -> tuple[str, str]:
    parsed = urlsplit(value)
    expected = {"https"} if https else {"http", "https"}
    if (
        parsed.scheme not in expected
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        schemes = "HTTPS" if https else "HTTP(S)"
        raise ValueError(f"{field} must be an origin-only {schemes} URL")
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}", parsed.hostname


def render(template: str, values: dict[str, str]) -> str:
    result = template
    for key, value in values.items():
        result = result.replace(f"__{key}__", value)
    unresolved = sorted(set(TOKEN.findall(result)))
    if unresolved:
        raise ValueError(f"unresolved template tokens: {', '.join(unresolved)}")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--backend-image", required=True)
    parser.add_argument("--admin-image", required=True)
    parser.add_argument("--web-image", required=True)
    parser.add_argument("--admin-origin", required=True)
    parser.add_argument("--web-origin", required=True)
    parser.add_argument("--casdoor-origin", required=True)
    parser.add_argument("--casdoor-backchannel-origin")
    parser.add_argument("--casdoor-namespace", default="app-platform-dev")
    parser.add_argument("--tls-secret", required=True)
    parser.add_argument("--image-pull-secret", default="harbor-registry-secret")
    parser.add_argument("--ingress-namespace", default="kube-system")
    parser.add_argument(
        "--ingress-pod-label-key", default="app.kubernetes.io/name"
    )
    parser.add_argument("--ingress-pod-label-value", default="traefik")
    parser.add_argument("--redis-host", default="redis-sunmoonai.data-platform-dev.svc.cluster.local")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--redis-db", type=int, default=0)
    parser.add_argument("--casdoor-organization", default="sunmoonai")
    parser.add_argument("--admin-client-id")
    parser.add_argument("--web-client-id")
    parser.add_argument("--admin-application")
    parser.add_argument("--web-application")
    parser.add_argument("--api-replicas", type=int, default=2)
    parser.add_argument("--worker-replicas", type=int, default=1)
    parser.add_argument("--admin-replicas", type=int, default=2)
    parser.add_argument("--web-replicas", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = dns_label(args.app, field="app", max_length=24)
    namespace = dns_label(args.namespace, field="namespace")
    release_id = dns_label(args.release_id, field="release-id", max_length=24)
    dns_label(args.tls_secret, field="tls-secret")
    dns_label(args.image_pull_secret, field="image-pull-secret")
    dns_label(args.ingress_namespace, field="ingress-namespace")
    dns_label(args.casdoor_namespace, field="casdoor-namespace")
    dns_label(args.ingress_pod_label_value, field="ingress-pod-label-value")
    if not LABEL_KEY.fullmatch(args.ingress_pod_label_key):
        raise ValueError("ingress-pod-label-key is not a Kubernetes label key")
    if len(f"{app}-backend-migration-{release_id}") > 63:
        raise ValueError("app and release-id produce a migration Job name over 63 chars")
    if not 1 <= args.redis_port <= 65535 or not 0 <= args.redis_db <= 15:
        raise ValueError("Redis port/db is outside the accepted template range")
    for field in ("api_replicas", "worker_replicas", "admin_replicas", "web_replicas"):
        if not 1 <= getattr(args, field) <= 20:
            raise ValueError(f"{field.replace('_', '-')} must be between 1 and 20")

    admin_origin, admin_host = strict_origin(
        args.admin_origin, field="admin-origin"
    )
    web_origin, web_host = strict_origin(args.web_origin, field="web-origin")
    casdoor_origin, _ = strict_origin(args.casdoor_origin, field="casdoor-origin")
    backchannel, _ = strict_origin(
        args.casdoor_backchannel_origin or casdoor_origin,
        field="casdoor-backchannel-origin",
        https=False,
    )
    images = {
        "backend": immutable_image(args.backend_image, field="backend-image"),
        "admin": immutable_image(args.admin_image, field="admin-image"),
        "web": immutable_image(args.web_image, field="web-image"),
    }
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory must be absent or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    values = {
        "APP": app,
        "NAMESPACE": namespace,
        "RELEASE_ID": release_id,
        "BACKEND_IMAGE": images["backend"],
        "ADMIN_IMAGE": images["admin"],
        "WEB_IMAGE": images["web"],
        "ADMIN_ORIGIN": admin_origin,
        "ADMIN_HOST": admin_host,
        "WEB_ORIGIN": web_origin,
        "WEB_HOST": web_host,
        "CASDOOR_ORIGIN": casdoor_origin,
        "CASDOOR_BACKCHANNEL_ORIGIN": backchannel,
        "CASDOOR_NAMESPACE": args.casdoor_namespace,
        "TLS_SECRET": args.tls_secret,
        "IMAGE_PULL_SECRET": args.image_pull_secret,
        "INGRESS_NAMESPACE": args.ingress_namespace,
        "INGRESS_POD_LABEL_KEY": args.ingress_pod_label_key,
        "INGRESS_POD_LABEL_VALUE": args.ingress_pod_label_value,
        "REDIS_HOST": args.redis_host,
        "REDIS_PORT": str(args.redis_port),
        "REDIS_DB": str(args.redis_db),
        "CASDOOR_ORGANIZATION": args.casdoor_organization,
        "ADMIN_CLIENT_ID": args.admin_client_id or f"sunmoonai-{app}-admin",
        "WEB_CLIENT_ID": args.web_client_id or f"sunmoonai-{app}-web",
        "ADMIN_APPLICATION": args.admin_application or f"sunmoonai-{app}-admin",
        "WEB_APPLICATION": args.web_application or f"sunmoonai-{app}-web",
        "API_REPLICAS": str(args.api_replicas),
        "WORKER_REPLICAS": str(args.worker_replicas),
        "ADMIN_REPLICAS": str(args.admin_replicas),
        "WEB_REPLICAS": str(args.web_replicas),
    }
    hashes: dict[str, str] = {}
    for filename in FILES:
        source = TEMPLATE_DIR / f"{filename}.tpl"
        target = output / filename
        content = render(source.read_text(encoding="utf-8"), values)
        target.write_text(content, encoding="utf-8")
        hashes[filename] = hashlib.sha256(content.encode()).hexdigest()

    secret_keys = (
        "ADMIN_CASDOOR_CLIENT_SECRET",
        "API_CELERY_BROKER_URL",
        "API_DATABASE_URL",
        "MIGRATION_DATABASE_URL",
        "REDIS_PASSWORD",
        "SCHEDULER_CELERY_BROKER_URL",
        "SCHEDULER_DATABASE_URL",
        "WEB_CASDOOR_CLIENT_SECRET",
        "WORKER_CELERY_BROKER_URL",
        "WORKER_DATABASE_URL",
    )
    optional_secret_keys = (
        "WORKER_CELERY_RESULT_BACKEND",
        "WORKER_DOWNSTREAM_CLIENT_SECRET",
    )
    (output / "required-secret-keys.txt").write_text(
        "\n".join(secret_keys) + "\n", encoding="utf-8"
    )
    (output / "optional-secret-keys.txt").write_text(
        "\n".join(optional_secret_keys) + "\n", encoding="utf-8"
    )
    release = {
        "schema_version": 1,
        "architecture": "app-platform-v2",
        "app": app,
        "namespace": namespace,
        "release_id": release_id,
        "images": images,
        "origins": {"admin": admin_origin, "web": web_origin, "casdoor": casdoor_origin},
        "resources": list(FILES),
        "sha256": hashes,
        "secret_name": f"{app}-backend-runtime",
        "secret_keys": list(secret_keys),
        "optional_secret_keys": list(optional_secret_keys),
        "dependencies": {
            "image_pull_secret": args.image_pull_secret,
            "tls_secret": args.tls_secret,
            "casdoor_namespace": args.casdoor_namespace,
            "ingress_namespace": args.ingress_namespace,
        },
        "formal_release": False,
    }
    (output / "release.json").write_text(
        json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": "rendered", **release}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
