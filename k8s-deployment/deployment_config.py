#!/usr/bin/env python3
"""Strict, credential-free deployment configuration for App Platform bundles."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Iterable


class ConfigError(RuntimeError):
    pass


KEY = re.compile(r"^[A-Z][A-Z0-9_]*$")
UNSAFE_UNQUOTED = re.compile(r"[\s`$();|&<>]")

BASE_KEYS = {
    "CONFIG_VERSION",
    "APP",
    "DEFAULT_PROFILE",
    "BUNDLE_DIR",
    "DEPLOY_SCRIPT",
    "NAMESPACE",
    "RELEASE_ID",
    "BACKEND_IMAGE",
    "ADMIN_IMAGE",
    "WEB_IMAGE",
    "ADMIN_ORIGIN",
    "WEB_ORIGIN",
    "CASDOOR_ORIGIN",
    "API_REPLICAS",
    "WORKER_REPLICAS",
    "SCHEDULER_REPLICAS",
    "ADMIN_REPLICAS",
    "WEB_REPLICAS",
}
PROFILE_KEYS = {
    "PROFILE_VERSION",
    "PROFILE_ENABLED",
    "KUBECONFIG",
    "TIMEOUT",
    "DISABLED_REASON",
}


def _decode_value(raw: str, *, path: Path, line: int) -> str:
    value = raw.strip()
    if not value:
        raise ConfigError(f"{path}:{line}: empty values are forbidden")
    if value[0] in {'\"', "'"}:
        try:
            decoded = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise ConfigError(f"{path}:{line}: invalid quoted value") from exc
        if not isinstance(decoded, str) or not decoded:
            raise ConfigError(f"{path}:{line}: expected a non-empty string")
        return decoded
    if "#" in value or UNSAFE_UNQUOTED.search(value):
        raise ConfigError(
            f"{path}:{line}: quote values containing whitespace or shell syntax"
        )
    return value


def load_conf(
    path: Path,
    *,
    allowed: set[str],
    required: Iterable[str],
) -> dict[str, str]:
    if not path.is_file():
        raise ConfigError(f"missing deployment config: {path}")
    result: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export ") or "=" not in line:
            raise ConfigError(f"{path}:{number}: expected KEY=VALUE without export")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not KEY.fullmatch(key) or key not in allowed:
            raise ConfigError(f"{path}:{number}: unknown configuration key {key!r}")
        if key in result:
            raise ConfigError(f"{path}:{number}: duplicate configuration key {key}")
        result[key] = _decode_value(raw_value, path=path, line=number)
    missing = sorted(set(required) - result.keys())
    if missing:
        raise ConfigError(f"{path}: missing configuration keys: {missing}")
    return result


def _integer(config: dict[str, str], key: str, minimum: int, maximum: int) -> int:
    try:
        value = int(config[key])
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{key} must be between {minimum} and {maximum}")
    return value


def load_base(path: Path) -> dict[str, str]:
    config = load_conf(path, allowed=BASE_KEYS, required=BASE_KEYS)
    if config["CONFIG_VERSION"] != "1":
        raise ConfigError("unsupported CONFIG_VERSION")
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,23}", config["APP"]):
        raise ConfigError("APP must be a lowercase DNS-style logical App name")
    if not re.fullmatch(r"[A-Z][A-Z0-9_-]*", config["DEFAULT_PROFILE"]):
        raise ConfigError("DEFAULT_PROFILE must be an uppercase profile name")
    for key in (
        "API_REPLICAS",
        "WORKER_REPLICAS",
        "SCHEDULER_REPLICAS",
        "ADMIN_REPLICAS",
        "WEB_REPLICAS",
    ):
        _integer(config, key, 1, 20)
    return config


def load_profile(path: Path) -> dict[str, str]:
    config = load_conf(
        path,
        allowed=PROFILE_KEYS,
        required={"PROFILE_VERSION", "PROFILE_ENABLED"},
    )
    if config["PROFILE_VERSION"] != "1":
        raise ConfigError("unsupported PROFILE_VERSION")
    if config["PROFILE_ENABLED"] not in {"true", "false"}:
        raise ConfigError("PROFILE_ENABLED must be true or false")
    if config["PROFILE_ENABLED"] == "false":
        reason = config.get("DISABLED_REASON", "profile has not passed a release gate")
        raise ConfigError(f"deployment profile is disabled: {reason}")
    missing = sorted({"KUBECONFIG", "TIMEOUT"} - config.keys())
    if missing:
        raise ConfigError(f"enabled profile is missing keys: {missing}")
    _integer(config, "TIMEOUT", 30, 3600)
    return config


def resolve_inside(root: Path, configured: str, *, field: str) -> Path:
    candidate = (root / configured).expanduser().resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ConfigError(f"{field} must resolve inside the App deployment root") from exc
    return candidate


def validate_release(config: dict[str, str], release: dict[str, Any]) -> None:
    expected = {
        "APP": release.get("logical_app", release.get("app")),
        "NAMESPACE": release.get("namespace"),
        "RELEASE_ID": release.get("release_id"),
        "BACKEND_IMAGE": release.get("images", {}).get("backend"),
        "ADMIN_IMAGE": release.get("images", {}).get("admin"),
        "WEB_IMAGE": release.get("images", {}).get("web"),
        "ADMIN_ORIGIN": release.get("origins", {}).get("admin"),
        "WEB_ORIGIN": release.get("origins", {}).get("web"),
        "CASDOOR_ORIGIN": release.get("origins", {}).get("casdoor"),
    }
    resource_app = release.get("resource_app", release.get("app"))
    replicas = release.get("deployment_replicas", {})
    expected.update(
        {
            "API_REPLICAS": replicas.get(f"{resource_app}-backend-api"),
            "WORKER_REPLICAS": replicas.get(f"{resource_app}-backend-worker"),
            "SCHEDULER_REPLICAS": replicas.get(f"{resource_app}-backend-scheduler"),
            "ADMIN_REPLICAS": replicas.get(f"{resource_app}-admin-frontend"),
            "WEB_REPLICAS": replicas.get(f"{resource_app}-web-frontend"),
        }
    )
    mismatches = {
        key: {"config": config[key], "release": value}
        for key, value in expected.items()
        if value is None or str(value) != config[key]
    }
    if mismatches:
        raise ConfigError(
            "deployment config differs from the immutable release; render and gate a "
            f"new release instead of overriding it at runtime: {json.dumps(mismatches, ensure_ascii=False)}"
        )

