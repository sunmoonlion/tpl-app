"""B7 identity lifecycle rehearsal on owned disposable resources, never live systems.

Uses each sibling Backend's real migrations and reviewed permission compiler.
This is not a business cutover, a secret provisioner, or independent UAT.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import asyncpg
import httpx
import pytest
from amqp.exceptions import AccessRefused, ConnectionForced, NotAllowed
from kombu import Connection, Producer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_runtime_broker_policy import BACKEND, channel, docker

sys.path.insert(0, str(BACKEND))

from app.application.services.durable_tasks import enqueue_task
from permission_pg_support import denied, execute, inventory
from runtime_database_policy import PolicyError, identifier
from test_runtime_broker_policy import (
    broker as broker,  # noqa: PLC0414
)
from test_runtime_broker_policy import (
    instance as instance,  # noqa: PLC0414
)
from test_runtime_identity_joint import (
    database as database,  # noqa: PLC0414
)
from test_runtime_identity_joint import database_compiler, eventually
from test_runtime_identity_joint import (
    postgres as postgres,  # noqa: PLC0414
)


async def test_grants_reapply_and_future_table_stays_denied(database):
    db = database
    compiler, _ = database_compiler()
    async with db.engines["migration"].begin() as connection:
        columns = await inventory(connection)
        statements = compiler(schema="public", principals=db.names, columns=columns)
        for _ in range(2):
            for statement in statements:
                await connection.execute(text(statement))
    for role in db.names:
        assert await execute(db, role, "SELECT current_user") == db.names[role]
    for role in ("api", "worker"):
        await denied(db, role, "UPDATE alembic_version SET version_num=version_num")
        await denied(db, role, f"SET ROLE {identifier(db.names['migration'])}")
    await denied(db, "scheduler", "SELECT * FROM public.outbox_message")
    await execute(db, "migration", "CREATE TABLE b7v_future (id integer)")
    try:
        for role in ("api", "worker", "scheduler"):
            await denied(db, role, "SELECT * FROM public.b7v_future")
        async with db.engines["migration"].connect() as connection:
            with pytest.raises(PolicyError):
                compiler(
                    schema="public",
                    principals=db.names,
                    columns=await inventory(connection),
                )
    finally:
        await execute(db, "migration", "DROP TABLE b7v_future")


@pytest.mark.parametrize("role", ["api", "worker"])
async def test_nologin_does_not_drain_existing_connection(database, role):
    db = database
    options = {
        "host": db.url.host,
        "port": db.url.port,
        "database": db.database,
        "user": db.names[role],
        "password": db.passwords[role],
        "timeout": 3,
        "command_timeout": 3,
    }
    old = await asyncpg.connect(**options)
    try:
        pid = await old.fetchval("SELECT pg_backend_pid()")
        await db.admin.execute(f"ALTER ROLE {identifier(db.names[role])} NOLOGIN")
        with pytest.raises(asyncpg.InvalidAuthorizationSpecificationError) as caught:
            await asyncpg.connect(**options)
        assert caught.value.sqlstate == "28000"
        # NOLOGIN is not a fence for already-authenticated pooled connections.
        assert await old.fetchval("SELECT current_user") == db.names[role]
        assert await old.fetchval("SELECT count(*) FROM outbox_message") == 0
        row = await db.admin.fetchrow(
            "SELECT datname, usename FROM pg_stat_activity WHERE pid=$1", pid
        )
        assert tuple(row) == (db.database, db.names[role])
        assert await db.admin.fetchval("SELECT pg_terminate_backend($1)", pid)

        async def absent():
            return not await db.admin.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE pid=$1)", pid
            )

        await eventually(absent, "exact owned old PostgreSQL connection drained")
        with pytest.raises(asyncpg.InvalidAuthorizationSpecificationError):
            await asyncpg.connect(**options)
        other = "worker" if role == "api" else "api"
        assert await execute(db, other, "SELECT current_user") == db.names[other]
    finally:
        await old.close()


def pg_binary(container, db, command, *arguments, data=None):
    """Credentials enter via env; binary archive stays in memory, never in logs."""
    __tracebackhide__ = True
    assert (
        docker(
            "inspect",
            container,
            "--format",
            '{{index .Config.Labels "luna.disposable"}}',
        )
        == "b7u"
    )
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "-e",
            "PGPASSWORD",
            container,
            command,
            "--host=127.0.0.1",
            "--username=postgres",
            "--no-password",
            *arguments,
        ],
        input=data,
        capture_output=True,
        timeout=45,
        check=False,
        env={**os.environ, "PGPASSWORD": db.url.password},
    )
    if result.returncode:
        diagnostic = result.stderr.decode(errors="replace")
        for secret in [db.url.password, *db.passwords.values()]:
            diagnostic = diagnostic.replace(secret, "<redacted>")
        raise AssertionError(f"{command} failed: {diagnostic}")
    return result.stdout


async def snapshot(db):
    async with db.engines["migration"].connect() as connection:
        columns = await inventory(connection)
        rows = {}
        assert "outbox_message" in columns and "inbox_message" in columns
        for table in sorted(columns):
            rows[table] = sorted(
                (
                    await connection.execute(
                        text(
                            f"SELECT row_to_json(t)::text FROM public.{identifier(table)} t"
                        )
                    )
                )
                .scalars()
                .all()
            )
        return columns, rows


async def test_dump_restore_preserves_schema_receipts_dedup_and_acl(database, postgres):
    db = database
    async with db.sessions["api"]() as session, session.begin():
        message_id = await enqueue_task(
            session,
            topic="test.backup.v1",
            key="backup",
            payload={"synthetic": True},
            deduplication_key="b7v-backup",
        )
    await execute(
        db,
        "worker",
        """
        INSERT INTO inbox_message(consumer, message_id)
        VALUES ('b7v-synthetic', :id)
    """,
        {"id": message_id},
    )
    before = await snapshot(db)
    archive = await asyncio.to_thread(
        pg_binary, postgres, db, "pg_dump", "--format=custom", db.database
    )
    assert archive.startswith(b"PGDMP") and len(archive) > 1000
    target = db.database + "_restore"
    engines = {}
    await db.admin.execute(
        f"CREATE DATABASE {identifier(target)} OWNER {identifier(db.names['migration'])}"
    )
    try:
        # Database CONNECT is cluster-level configuration, not inside pg_dump.
        await db.admin.execute(
            f"REVOKE ALL ON DATABASE {identifier(target)} FROM PUBLIC"
        )
        for role in ("api", "worker", "scheduler"):
            await db.admin.execute(
                f"GRANT CONNECT ON DATABASE {identifier(target)} TO {identifier(db.names[role])}"
            )
        await asyncio.to_thread(
            pg_binary,
            postgres,
            db,
            "pg_restore",
            "--exit-on-error",
            "--dbname=" + target,
            data=archive,
        )
        for role, source in db.engines.items():
            engines[role] = create_async_engine(
                source.url.set(database=target),
                poolclass=NullPool,
                hide_parameters=True,
                connect_args={"timeout": 5, "command_timeout": 5},
            )
        restored = SimpleNamespace(
            engines=engines,
            sessions={
                r: async_sessionmaker(e, expire_on_commit=False)
                for r, e in engines.items()
            },
        )
        assert await snapshot(restored) == before
        for role in db.names:
            assert (
                await execute(restored, role, "SELECT current_user") == db.names[role]
            )
        for role in ("api", "worker"):
            await denied(
                restored, role, "UPDATE alembic_version SET version_num=version_num"
            )
            await denied(
                restored, role, f"SET ROLE {identifier(db.names['migration'])}"
            )
        await denied(restored, "scheduler", "SELECT * FROM public.outbox_message")
        async with restored.sessions["api"]() as session, session.begin():
            duplicate = await enqueue_task(
                session,
                topic="test.backup.v1",
                key="backup",
                payload={"synthetic": True},
                deduplication_key="b7v-backup",
            )
        assert duplicate == message_id
        assert await execute(restored, "api", "SELECT count(*) FROM inbox_message") == 1
        assert (
            await execute(restored, "api", "SELECT count(*) FROM outbox_message") == 1
        )
        # Restore/replay touched only the isolated target, never the source database.
        assert await snapshot(db) == before
        print(
            f"backup restored: {len(before[0])} tables; schema/data/ACL/dedup verified"
        )
    finally:
        for engine in engines.values():
            await engine.dispose()
        await db.admin.execute(f"DROP DATABASE {identifier(target)}")


def assert_broker_plan(instance):
    for permission in instance.plan["permissions"]:
        actual = instance.api(
            "GET", f"permissions/{instance.vhost}/{permission['user']}"
        )
        assert {key: actual[key] for key in permission} == permission
    for kind in ("queues", "exchanges"):
        for expected in instance.plan[kind]:
            actual = instance.api("GET", f"{kind}/{instance.vhost}/{expected['name']}")
            canonical = dict(expected)
            if kind == "queues":
                # Pinned broker materializes the default; reject every other argument.
                assert actual["type"] == "classic"
                assert expected["arguments"] == {}
                canonical["arguments"] = {"x-queue-type": "classic"}
            assert {key: actual[key] for key in canonical} == canonical
    actual = instance.api("GET", f"bindings/{instance.vhost}")
    for expected in instance.plan["bindings"]:
        assert (
            sum({key: row[key] for key in expected} == expected for row in actual) == 1
        )


def test_broker_reimport_restart_keeps_acl_topology_and_persistent_message(instance):
    for _ in range(2):
        instance.api("POST", "definitions", instance.plan)
    assert_broker_plan(instance)
    with channel(instance, "api") as ch:
        Producer(ch).publish(
            {"synthetic": "b7v-before-restart"},
            exchange=instance.queue,
            routing_key=instance.queue,
            serializer="json",
            delivery_mode=2,
        )
    assert (
        docker(
            "inspect",
            instance.container,
            "--format",
            '{{index .Config.Labels "luna.disposable"}}',
        )
        == "b7s"
    )
    docker("restart", "--time=15", instance.container)
    instance.refresh_endpoints()
    deadline = time.monotonic() + 45
    while True:
        try:
            assert_broker_plan(instance)
            break
        except (httpx.TransportError, AssertionError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.2)
    with channel(instance, "worker") as ch:
        message = ch.basic_get(instance.queue)
        assert message is not None
        assert json.loads(message.body) == {"synthetic": "b7v-before-restart"}
        ch.basic_ack(message.delivery_info["delivery_tag"])
    for role in ("api", "scheduler"):
        with channel(instance, role) as ch, pytest.raises(AccessRefused):
            ch.basic_get(instance.queue)


def test_broker_revocation_drains_only_owned_user_and_new_login_is_denied(instance):
    with Connection(instance.urls["api"], connect_timeout=3) as old:
        old.ensure_connection(max_retries=0)
        deadline = time.monotonic() + 15
        while True:
            rows = [
                row
                for row in instance.api("GET", "connections")
                if row["user"] == instance.names["api"]
                and row["vhost"] == instance.vhost
            ]
            if rows:
                break
            assert time.monotonic() < deadline, "owned connection not observed"
            time.sleep(0.2)
        assert len(rows) == 1
        instance.api("DELETE", f"permissions/{instance.vhost}/{instance.names['api']}")
        # Broker versions may close on permission removal; otherwise explicitly drain
        # only the exact connection identified above, never all vhost connections.
        names = {row["name"] for row in rows}
        for row in instance.api("GET", "connections"):
            if row["name"] in names:
                assert (row["user"], row["vhost"]) == (
                    instance.names["api"],
                    instance.vhost,
                )
                instance.api("DELETE", "connections/" + quote(row["name"], safe=""))
        # Receive the server's Connection.Close and send Close-Ok. An idle client
        # that never reads otherwise leaves the handshake pending after HTTP DELETE.
        with pytest.raises(ConnectionForced) as closed:
            old.drain_events(timeout=3)
        assert closed.value.reply_code == 320
        deadline = time.monotonic() + 15
        while any(row["name"] in names for row in instance.api("GET", "connections")):
            assert time.monotonic() < deadline, (
                "owned old broker connection not drained"
            )
            time.sleep(0.2)
        with pytest.raises((NotAllowed, AccessRefused)), channel(instance, "api"):
            pass
        with channel(instance, "worker") as ch:
            assert ch.queue_declare(instance.queue, passive=True)[1] == 0
    # Explicit candidate rollback: reapply the same frozen ACL, not a wildcard.
    instance.api("POST", "definitions", instance.plan)
    assert_broker_plan(instance)
    with channel(instance, "api") as ch:
        Producer(ch).publish(
            {"rollback": True},
            exchange=instance.queue,
            routing_key=instance.queue,
            serializer="json",
        )
    with channel(instance, "worker") as ch:
        message = ch.basic_get(instance.queue)
        assert message is not None and json.loads(message.body) == {"rollback": True}
        ch.basic_ack(message.delivery_info["delivery_tag"])
