"""Generic local test targets and disposable auxiliary services; no App imports."""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

MINIO = "sha256:a72bf37c235a83a73890d2a46c5b36801fed61c335175e0396070bf84a8bbb98"
REDIS = "sha256:9917e842cfc3220e4ac3e819eb98a975cc171eff5e532c79cb75558030eb9078"


def select_backend(deployment: Path, configured: str | None) -> Path:
    workspace = deployment.resolve().parent.parent
    backend = (
        Path(configured).resolve()
        if configured
        else deployment.parent / "tpl-backend/app"
    )
    backend = backend.resolve()
    app = backend.parent.parent
    if (
        app.parent != workspace
        or not re.fullmatch(r"[a-z][a-z0-9-]*-app", app.name)
        or backend.name != "app"
        or backend.parent.name != app.name.removesuffix("-app") + "-backend"
        or not (backend / "app/worker.py").is_file()
    ):
        raise ValueError("test Backend must be an initialized sibling App component")
    return backend


def select_auxiliary(value: str) -> str:
    if value not in {"none", "s3", "redis"}:
        raise ValueError("test auxiliary must be none, s3 or redis")
    return value


@contextmanager
def auxiliary_service(kind, docker):
    select_auxiliary(kind)
    if kind == "none":
        yield {}, ()
        return
    suffix = uuid4().hex
    password = secrets.token_urlsafe(24)
    arguments = [
        "run",
        "-d",
        "--pull=never",
        "--name",
        f"luna-b7t-{kind}-{suffix}",
        "--label",
        "luna.disposable=b7t",
        "--memory=640m",
        "--cpus=2",
    ]
    if kind == "s3":
        # Existing S3 fault fixture pins this endpoint and synthetic credentials.
        arguments += [
            "-p",
            "127.0.0.1:59039:9000",
            "-e",
            "MINIO_ROOT_USER",
            "-e",
            "MINIO_ROOT_PASSWORD",
            MINIO,
            "server",
            "/data",
            "--address",
            ":9000",
        ]
    else:
        arguments += [
            "-p",
            "127.0.0.1::6379",
            REDIS,
            "valkey-server",
            "--save",
            "",
            "--appendonly",
            "no",
            "--requirepass",
            password,
        ]
    container = docker(
        *arguments,
        env={
            **os.environ,
            "MINIO_ROOT_USER": "luna-test",
            "MINIO_ROOT_PASSWORD": "luna-disposable-test-only",
        },
    )
    volumes = []
    try:
        expected = MINIO if kind == "s3" else REDIS
        assert docker("inspect", container, "--format", "{{.Image}}") == expected
        mounts = json.loads(
            docker("inspect", container, "--format", "{{json .Mounts}}")
        )
        assert all(row["Type"] == "volume" for row in mounts)
        volumes = [row["Name"] for row in mounts]
        print(f"disposable {kind}: {container}; image={expected}; volumes={volumes}")
        address = docker("port", container, "9000" if kind == "s3" else "6379")
        assert address.startswith("127.0.0.1:")
        deadline = time.monotonic() + 30
        if kind == "s3":
            import httpx

            assert address == "127.0.0.1:59039"
            with httpx.Client(timeout=2, trust_env=False) as client:
                while True:
                    try:
                        if (
                            client.get(
                                f"http://{address}/minio/health/live"
                            ).status_code
                            == 200
                        ):
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() >= deadline:
                        raise AssertionError("disposable S3 unavailable")
                    time.sleep(0.2)
            yield {"ARTIFACT_TEST_S3_ENDPOINT": f"http://{address}"}, ()
        else:
            from redis.asyncio import Redis
            from redis.exceptions import RedisError

            url = f"redis://:{password}@{address}/0"

            async def wait_redis():
                client = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
                try:
                    while True:
                        try:
                            await client.ping()
                            return
                        except RedisError:
                            if time.monotonic() >= deadline:
                                raise AssertionError(
                                    "disposable Redis unavailable"
                                ) from None
                            await asyncio.sleep(0.2)
                finally:
                    await client.aclose()

            asyncio.run(wait_redis())
            yield {"AGENT_TEST_REDIS_URL": url}, (password,)
    finally:
        assert (
            docker(
                "inspect",
                container,
                "--format",
                '{{index .Config.Labels "luna.disposable"}}',
            )
            == "b7t"
        )
        docker("rm", "-f", "-v", container)
        assert (
            docker(
                "ps",
                "-a",
                "--no-trunc",
                "--filter",
                "id=" + container,
                "--format",
                "{{.ID}}",
            )
            == ""
        )
        for volume in volumes:
            assert (
                docker(
                    "volume",
                    "ls",
                    "--filter",
                    "name=" + volume,
                    "--format",
                    "{{.Name}}",
                )
                == ""
            )
        print(f"disposable {kind} and volumes removed: {container}")
