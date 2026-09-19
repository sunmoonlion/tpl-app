"""Joint restricted DB/broker runtime gate, exclusively fresh local Docker resources.

Run with the target backend venv and --asyncio-mode=auto. Both confirmations are
required; no external DB/broker URL is accepted or reused. Production leases,
storage, task transport, readiness, Beat and prefork/late-ACK defaults stay intact.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.exc import DBAPIError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from permission_pg_support import denied, execute, provision_database
from runtime_database_policy import template_grants
from test_runtime_broker_policy import (
    BACKEND,
    DEPLOYMENT,
    channel,
    docker,
)
from test_runtime_broker_policy import (
    broker as broker,  # noqa: PLC0414 -- pytest fixture re-export
)
from test_runtime_broker_policy import (
    instance as instance,  # noqa: PLC0414 -- pytest fixture re-export
)

PG_IMAGE = "sha256:dbd371582fbbb100b22b891e485f4559187362348c1d4b5d0a2191134807516b"
TOPIC = "test.joint.runtime.v1"


def database_compiler():
    app = BACKEND.parent.parent.name.removesuffix("-app")
    if app == "tpl":
        return template_grants, False
    if app not in {"info", "knowledge", "investment"}:
        raise ValueError("no reviewed database policy for this joint test target")
    path = (
        DEPLOYMENT.parent.parent
        / "k8s/sunmoonai/app-platform"
        / f"{app}-app/deployment/{app}_database_policy.py"
    )
    spec = importlib.util.spec_from_file_location(f"{app}_database_policy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, f"{app}_grants"), app == "info"


@pytest.fixture(scope="module")
def postgres():
    assert os.environ.get("JOINT_RUNTIME_TEST_CONFIRM") == "disposable-b7u-only"
    database_compiler()  # Reject unknown targets before allocating anything.
    password = secrets.token_hex(24)
    container = docker(
        "create",
        "--pull=never",
        "--name",
        "luna-b7u-pg-" + uuid4().hex,
        "--label",
        "luna.disposable=b7u",
        "--memory=640m",
        "--cpus=2",
        "-p",
        "127.0.0.1:55439:5432",
        "-e",
        "POSTGRESQL_PASSWORD",
        "-e",
        "POSTGRESQL_DATABASE=backlog_tests",
        PG_IMAGE,
        env={**os.environ, "POSTGRESQL_PASSWORD": password},
    )
    volumes = []
    try:
        assert docker("inspect", container, "--format", "{{.Image}}") == PG_IMAGE
        mounts = json.loads(
            docker("inspect", container, "--format", "{{json .Mounts}}")
        )
        assert all(row["Type"] == "volume" for row in mounts)
        volumes = [row["Name"] for row in mounts]
        print(f"joint PostgreSQL: {container}; image={PG_IMAGE}; volumes={volumes}")
        # Even a bind/start failure is inside teardown, with a known owned ID.
        docker("start", container)
        assert docker("port", container, "5432") == "127.0.0.1:55439"

        async def wait_ready():
            deadline = time.monotonic() + 40
            while True:
                try:
                    connection = await asyncpg.connect(
                        host="127.0.0.1",
                        port=55439,
                        user="postgres",
                        password=password,
                        database="backlog_tests",
                        timeout=2,
                    )
                    await connection.close()
                    return
                except (OSError, asyncpg.PostgresError):
                    if time.monotonic() >= deadline:
                        raise AssertionError(
                            "joint disposable PostgreSQL unavailable"
                        ) from None
                    await asyncio.sleep(0.2)

        asyncio.run(wait_ready())
        with pytest.MonkeyPatch.context() as environment:
            environment.setenv("RUNTIME_POLICY_TEST_CONFIRM", "disposable-b7u-only")
            environment.setenv(
                "RUNTIME_POLICY_TEST_DATABASE_URL",
                f"postgresql+asyncpg://postgres:{password}@127.0.0.1:55439/backlog_tests",
            )
            yield container
    finally:
        assert (
            docker(
                "inspect",
                container,
                "--format",
                '{{index .Config.Labels "luna.disposable"}}',
            )
            == "b7u"
        )
        docker("rm", "-f", "-v", container)
        assert (
            docker("ps", "-a", "--filter", "id=" + container, "--format", "{{.ID}}")
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
        print(f"joint PostgreSQL removed: {container}; volumes removed={len(volumes)}")


@pytest_asyncio.fixture
async def database(postgres):
    compiler, extension = database_compiler()
    async with provision_database(
        BACKEND, compiler, scope="b7u", uuid_extension=extension
    ) as value:
        yield value


class Runtime:
    def __init__(self, database, instance, directory):
        self.database, self.instance, self.directory = database, instance, directory
        self.secrets = [*database.passwords.values()]
        self.secrets.extend(urlparse(url).password for url in instance.urls.values())

    def __repr__(self):
        return "<joint test runtime credentials redacted>"

    def redact(self, value):
        for secret in self.secrets:
            value = value.replace(secret, "<redacted>")
        return value

    def env(self, role):
        # Do not hand provisioning/test-admin or another runtime's URLs to children.
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.endswith(("DATABASE_URL", "BROKER_URL"))
        }
        return {
            **environment,
            "DATABASE_URL": self.database.engines[role].url.render_as_string(
                hide_password=False
            ),
            "CELERY_BROKER_URL": self.instance.urls[role],
            "CELERY_QUEUE": self.instance.queue,
            "CELERY_RESULT_BACKEND": "",
            "CELERY_TASK_TOPOLOGY_PREDECLARED": "true",
            "JOINT_RUNTIME_TEST_CONTROL": str(self.directory),
            "PYTHONPATH": str(Path(__file__).parent) + os.pathsep + str(BACKEND),
        }

    def run(self, role, code, *args):
        __tracebackhide__ = True
        try:
            result = subprocess.run(
                [sys.executable, "-c", code, *args],
                cwd=BACKEND,
                env=self.env(role),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise AssertionError("joint runtime subprocess timed out") from None
        assert result.returncode == 0, self.redact(result.stdout + result.stderr)
        return result.stdout.strip()

    async def enqueue(self, key, **payload):
        # Actual application storage/configuration in a separate API-role process.
        result = await asyncio.to_thread(
            self.run,
            "api",
            """
import asyncio, json, sys
from sqlalchemy import text
from app.infrastructure.storage.postgres import get_postgres
from app.application.services.durable_tasks import enqueue_task
async def main():
    pg = get_postgres()
    await pg.init()
    try:
        async with pg.session_factory() as s, s.begin():
            identity = (await s.execute(text('SELECT current_user'))).scalar_one()
            payload = json.loads(sys.argv[1])
            identifier = await enqueue_task(s, topic='test.joint.runtime.v1',
                key=payload['key'], payload=payload, deduplication_key=payload['key'])
        print(json.dumps({'id': str(identifier), 'identity': identity}))
    finally:
        await pg.shutdown()
asyncio.run(main())
""",
            json.dumps({"key": key, **payload}),
        )
        row = json.loads(result)
        assert row["identity"] == self.database.names["api"]
        return row["id"]

    async def send(self, role, task, identifier=None):
        await asyncio.to_thread(
            self.run,
            role,
            """
import sys
from app.bootstrap.worker import celery_app
celery_app.send_task(sys.argv[1], args=sys.argv[2:])
""",
            task,
            *([identifier] if identifier else []),
        )

    @contextmanager
    def process(self, role):
        node = "b7u-" + uuid4().hex
        if role == "worker":
            args = [
                "-A",
                "runtime_identity_worker:celery_app",
                "worker",
                "--pool=prefork",
                "--concurrency=1",
                "--hostname=celery@" + node,
            ]
        else:
            args = [
                "-A",
                "app.bootstrap.scheduler:celery_app",
                "beat",
                "--max-interval=1",
                "--schedule",
                str(self.directory / ("beat-" + node)),
            ]
        path = self.directory / (node + ".log")
        with path.open("w") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "celery", *args, "--loglevel=WARNING"],
                cwd=BACKEND,
                env={**self.env(role), "POD_NAME": node},
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            try:
                yield process, node, path
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)

    async def ready(self, worker):
        process, node, log = worker

        async def probe():
            assert process.poll() is None, self.redact(log.read_text())
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-m", "app.cli.worker_readiness"],
                cwd=BACKEND,
                env={**self.env("worker"), "POD_NAME": node},
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return result.returncode == 0

        await eventually(probe, "real Worker readiness", timeout=35)
        with channel(self.instance, "worker") as ch:
            assert ch.queue_declare(self.instance.queue, passive=True)[2] == 1

    async def receipts(self, identifier):
        return await execute(
            self.database,
            "api",
            "SELECT count(*) FROM inbox_message WHERE message_id=CAST(:id AS uuid)",
            {"id": identifier},
        )

    async def effect(self, key):
        return await execute(
            self.database,
            "api",
            "SELECT payload->>'worker_identity' FROM outbox_message WHERE deduplication_key=:key",
            {"key": "effect:" + key},
        )

    async def drained(self, min_acks=1):
        row = await asyncio.to_thread(
            self.instance.api,
            "GET",
            f"queues/{self.instance.vhost}/{self.instance.queue}",
        )
        # Require observed counters, not absent/stale fields defaulted to zero.
        return (
            row.get("messages_ready") == 0
            and row.get("messages_unacknowledged") == 0
            and row.get("message_stats", {}).get("ack", 0) >= min_acks
        )


async def eventually(probe, label, *, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await probe():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("deadline waiting for " + label)


@pytest.fixture
def runtime(database, instance, tmp_path):
    return Runtime(database, instance, tmp_path)


async def test_joint_beat_pump_consume_commit_ack_and_duplicate(runtime):
    db = runtime.database
    for role in ("api", "worker", "scheduler"):
        environment = runtime.env(role)
        assert "RUNTIME_POLICY_TEST_DATABASE_URL" not in environment
        assert "MIGRATION_DATABASE_URL" not in environment
        assert {
            key for key in environment if key.endswith(("DATABASE_URL", "BROKER_URL"))
        } == {"DATABASE_URL", "CELERY_BROKER_URL"}
    for role, name in db.names.items():
        assert await execute(db, role, "SELECT current_user") == name
    # Without public USAGE an unqualified name is hidden by search_path (42P01).
    # Qualify it to prove the actual schema privilege denial (42501), not absence.
    with pytest.raises(DBAPIError) as hidden:
        await execute(db, "scheduler", "SELECT * FROM outbox_message")
    assert hidden.value.orig.sqlstate == "42P01"
    await denied(db, "scheduler", "SELECT * FROM public.outbox_message")
    first = await runtime.enqueue("one")
    assert await runtime.enqueue("one") == first
    with runtime.process("worker") as worker, runtime.process("scheduler") as beat:
        await runtime.ready(worker)
        await eventually(
            lambda: runtime.receipts(first), "Beat -> pump -> committed Inbox"
        )
        assert beat[0].poll() is None
        assert await runtime.effect("one") == db.names["worker"]
        observed_users = []

        async def both_broker_identities():
            connections = await asyncio.to_thread(
                runtime.instance.api, "GET", "connections"
            )
            users = {
                row["user"]
                for row in connections
                if row["vhost"] == runtime.instance.vhost
            }
            roles = sorted(
                role
                for role in ("worker", "scheduler")
                if runtime.instance.names[role] in users
            )
            if not observed_users or roles != observed_users[-1]:
                observed_users.append(roles)
            return roles == ["scheduler", "worker"]

        # Management's sampled connection inventory can lag an already committed task.
        await eventually(both_broker_identities, "both actual broker login identities")
        print(f"observed broker identity samples: {observed_users}")
        await runtime.send("api", "app.tasks.durable_delivery.execute", first)
        barrier = await runtime.enqueue("barrier")
        await runtime.send("scheduler", "app.tasks.durable_delivery.execute", barrier)
        await eventually(
            lambda: runtime.receipts(barrier), "duplicate ordering barrier"
        )
        assert await runtime.receipts(first) == 1
        assert (
            await execute(
                db,
                "api",
                "SELECT count(*) FROM outbox_message WHERE deduplication_key='effect:one'",
            )
            == 1
        )
        await eventually(
            lambda: runtime.drained(4), "broker ACK after committed effects"
        )


async def test_joint_failed_handler_rolls_back_then_explicit_retry(runtime):
    identifier = await runtime.enqueue("failure", fail=True)
    with runtime.process("worker") as worker:
        await runtime.ready(worker)
        await runtime.send("scheduler", "app.tasks.durable_delivery.pump")

        async def failed():
            return "synthetic-joint-rollback" in worker[2].read_text()

        await eventually(failed, "actual handler failure")
        await eventually(lambda: runtime.drained(2), "failed task broker ACK")
        assert await runtime.receipts(identifier) == 0
        assert await runtime.effect("failure") is None
        # Broker ACK alone is explicitly NOT a committed business receipt.
        (runtime.directory / "release-failure").touch()
        await runtime.send("api", "app.tasks.durable_delivery.execute", identifier)
        await eventually(lambda: runtime.receipts(identifier), "explicit retry commit")
        assert await runtime.effect("failure") == runtime.database.names["worker"]
        await eventually(lambda: runtime.drained(3), "retry broker ACK")


async def test_joint_killed_worker_rolls_back_and_default_lease_recovers(runtime):
    identifier = await runtime.enqueue("crash", crash=True)
    with runtime.process("worker") as worker:
        await runtime.ready(worker)
        await runtime.send("scheduler", "app.tasks.durable_delivery.pump")

        async def open_transaction():
            return (runtime.directory / "transaction-open").exists()

        await eventually(open_transaction, "open handler transaction")

        async def unacknowledged():
            row = await asyncio.to_thread(
                runtime.instance.api,
                "GET",
                f"queues/{runtime.instance.vhost}/{runtime.instance.queue}",
            )
            return row.get("messages_unacknowledged", 0) >= 1

        await eventually(unacknowledged, "actual outstanding broker delivery")
        assert await runtime.receipts(identifier) == 0
        assert await runtime.effect("crash") is None
        epoch = await execute(
            runtime.database,
            "api",
            "SELECT epoch FROM outbox_execution WHERE message_id=CAST(:id AS uuid)",
            {"id": identifier},
        )
        assert epoch == 1
        # Exact process group created by this fixture, never a discovered/shared PID.
        assert os.getpgid(worker[0].pid) == worker[0].pid
        os.killpg(worker[0].pid, signal.SIGKILL)
        await asyncio.to_thread(worker[0].wait, timeout=5)
    assert await runtime.receipts(identifier) == 0
    assert await runtime.effect("crash") is None
    (runtime.directory / "release-crash").touch()
    # Do not shorten the production 60-second lease or manipulate DB timestamps.
    with runtime.process("worker") as restarted, runtime.process("scheduler"):
        await runtime.ready(restarted)
        await eventually(
            lambda: runtime.receipts(identifier),
            "default lease + Beat recovery",
            timeout=95,
        )
        assert await runtime.effect("crash") == runtime.database.names["worker"]
        assert (
            await execute(
                runtime.database,
                "api",
                "SELECT epoch FROM outbox_execution WHERE message_id=CAST(:id AS uuid)",
                {"id": identifier},
            )
            > epoch
        )
        assert (
            await execute(
                runtime.database,
                "api",
                "SELECT attempt_count FROM outbox_message WHERE id=CAST(:id AS uuid)",
                {"id": identifier},
            )
            >= 2
        )
        await eventually(runtime.drained, "recovered task broker ACK")
