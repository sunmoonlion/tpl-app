"""Real disposable-PG gate; missing test authorization is an error, not skip.

Never point this fixture at a business PostgreSQL. It creates uniquely named
databases and LOGIN roles and removes only those exact objects in teardown.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest
import pytest_asyncio

DEPLOYMENT = Path(__file__).resolve().parents[1]
BACKEND = DEPLOYMENT.parent / "tpl-backend/app"
sys.path.insert(0, str(DEPLOYMENT))
sys.path.insert(0, str(BACKEND))
import runtime_database_policy as policy
from app.application.services import auth_service
from app.application.services.durable_tasks import DurableTasks, enqueue_task
from app.infrastructure.messaging.delivery_observation import collect_delivery_snapshot
from app.infrastructure.messaging.durable_delivery import DeliveryLeaseLost
from app.infrastructure.storage.schema_readiness import verify_schema_revision
from app.tasks.durable_delivery import pump
from permission_pg_support import denied, execute, inventory, provision_database

TOPIC = "test.permission.v1"


@pytest_asyncio.fixture
async def database():
    async with provision_database(BACKEND, policy.template_grants) as instance:
        yield instance


async def enqueue(database, key="one", payload=None):
    async with database.sessions["api"]() as session, session.begin():
        return await enqueue_task(
            session,
            topic=TOPIC,
            key="permission:one",
            payload=payload or {},
            deduplication_key=key,
        )


async def test_real_login_identities_schema_readiness_and_owner(database):
    for role, name in database.names.items():
        assert await execute(database, role, "SELECT current_user") == name
        assert await execute(database, role, "SELECT session_user") == name
        assert (
            await execute(
                database,
                role,
                "SELECT rolsuper FROM pg_roles WHERE rolname=current_user",
            )
            is False
        )
        if role in ("api", "worker"):
            async with database.sessions[role]() as session:
                await verify_schema_revision(session)
    assert (
        await execute(
            database,
            "migration",
            "SELECT bool_and(tableowner=current_user) FROM pg_tables WHERE schemaname='public'",
        )
        is True
    )


async def test_api_real_identity_upsert_and_immutable_binding(database, monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "get_postgres",
        lambda: SimpleNamespace(session_factory=database.sessions["api"]),
    )
    service = auth_service.AuthService("admin")
    first = await service._load_or_create_user(
        "https://issuer.example.test", "one", {"name": "First"}
    )
    updated = await service._load_or_create_user(
        "https://issuer.example.test", "one", {"name": "Updated"}
    )
    assert first["id"] == updated["id"]
    assert updated["display_name"] == "Updated"
    await denied(database, "api", "UPDATE auth_user SET subject='another'")
    await denied(database, "api", "DELETE FROM auth_user")
    await denied(database, "worker", "SELECT * FROM auth_user")


async def test_api_intent_dedup_and_consumer_state_denials(database):
    message = await enqueue(database)
    assert await enqueue(database) == message
    with pytest.raises(ValueError, match="different intent"):
        await enqueue(database, payload={"changed": True})
    for sql in (
        "UPDATE outbox_message SET status='published'",
        "UPDATE outbox_message SET lease_owner='forged'",
        "UPDATE outbox_message SET payload='{}'::jsonb",
        "INSERT INTO outbox_message (id,status) VALUES (gen_random_uuid(),'published')",
        "INSERT INTO inbox_message (consumer,message_id) VALUES ('test',:id)",
        "UPDATE outbox_execution SET epoch=epoch+1",
        "UPDATE outbox_dead_letter SET replayed_at=clock_timestamp()",
    ):
        await denied(database, "api", sql, {"id": message})


async def test_worker_pump_consume_duplicate_and_api_metrics(database):
    message = await enqueue(database)

    async def handler(session, payload):
        # Real transactional handler effect: enqueue a follow-on intent.
        await enqueue_task(
            session,
            topic="test.followup.v1",
            key="followup:one",
            payload={},
            deduplication_key="followup",
        )

    delivery = DurableTasks(database.sessions["worker"], handlers={TOPIC: handler})
    published = []

    async def publish(row):
        published.append(row["id"])

    assert await pump(delivery, publish) == 1
    assert published == [message]
    assert await delivery.consume(message) is True
    assert await delivery.consume(message) is False
    assert await execute(database, "api", "SELECT count(*) FROM inbox_message") == 1
    assert await execute(database, "api", "SELECT count(*) FROM outbox_message") == 2
    snapshot = await collect_delivery_snapshot(
        database.sessions["api"], {"permission": delivery}
    )
    assert snapshot["topics"][0]["retained_receipt_messages"] == 1


async def test_worker_failure_rollback_dead_letter_replay_and_reconcile(database):
    message = await enqueue(database)

    async def fail_handler(session, payload):
        await enqueue_task(
            session,
            topic="test.followup.v1",
            key="followup:one",
            payload={},
            deduplication_key="rolled-back",
        )
        raise RuntimeError("synthetic handler failure")

    failing = DurableTasks(
        database.sessions["worker"], handlers={TOPIC: fail_handler}, max_attempts=1
    )
    with pytest.raises(RuntimeError, match="synthetic handler"):
        await failing.consume(message)
    assert await execute(database, "api", "SELECT count(*) FROM outbox_message") == 1
    assert await execute(database, "api", "SELECT count(*) FROM inbox_message") == 0

    async def fail_publish(row):
        raise ConnectionError("synthetic failure")

    assert await pump(failing, fail_publish) == 1
    assert await failing.claim_delivery() is None
    assert (
        await execute(
            database,
            "api",
            "SELECT count(*) FROM outbox_dead_letter WHERE replayed_at IS NULL",
        )
        == 1
    )
    await failing.replay(message)
    assert await failing.claim_delivery() is not None
    # Exercise the reconciler with a synthetic lost broker receipt.
    await execute(
        database,
        "worker",
        "UPDATE outbox_message SET status='published', published_at=clock_timestamp()-interval '2 hours', attempt_count=1",
    )
    recovering = DurableTasks(
        database.sessions["worker"], handlers={TOPIC: fail_handler}, max_attempts=3
    )
    assert await recovering.reconcile() == 1


@pytest.mark.parametrize("role", ["api", "worker", "scheduler"])
async def test_runtime_cannot_change_version_ddl_owners_or_delete_receipts(
    database, role
):
    for statement in (
        "UPDATE public.alembic_version SET version_num='forged'",
        "INSERT INTO public.alembic_version VALUES ('forged')",
        "DELETE FROM public.alembic_version",
        "CREATE TABLE public.forbidden (id integer)",
        "CREATE SCHEMA forbidden",
        "CREATE TEMP TABLE forbidden (id integer)",
        "ALTER TABLE public.outbox_message ADD COLUMN forbidden integer",
        "DROP TABLE public.outbox_message",
        "TRUNCATE public.inbox_message",
        "DELETE FROM public.inbox_message",
        "DELETE FROM public.outbox_execution",
        "DELETE FROM public.outbox_dead_letter",
        "DELETE FROM public.outbox_message",
        f"SET ROLE {policy.identifier(database.names['migration'])}",
    ):
        await denied(database, role, statement)
    if role == "scheduler":
        await denied(database, role, "SELECT * FROM public.outbox_message")
        await denied(database, role, "SELECT * FROM public.alembic_version")


@pytest.mark.parametrize("role", ["api", "worker", "scheduler", "migration"])
async def test_cross_database_connection_denied(database, role):
    with pytest.raises(asyncpg.InsufficientPrivilegeError) as caught:
        await asyncpg.connect(
            host=database.url.host,
            port=database.url.port,
            database=database.other,
            user=database.names[role],
            password=database.passwords[role],
            timeout=5,
        )
    assert caught.value.sqlstate == "42501"


@pytest.mark.parametrize("role", ["api", "worker", "scheduler"])
async def test_runtime_password_cannot_authenticate_as_migration(database, role):
    assert len(set(database.passwords.values())) == 4
    assert all(
        password not in repr(database) for password in database.passwords.values()
    )
    with pytest.raises(asyncpg.InvalidPasswordError) as caught:
        await asyncpg.connect(
            host=database.url.host,
            port=database.url.port,
            database=database.database,
            user=database.names["migration"],
            password=database.passwords[role],
            timeout=5,
        )
    assert caught.value.sqlstate == "28P01"


async def test_api_uncommitted_intent_rolls_back(database):
    with pytest.raises(RuntimeError, match="synthetic rollback"):
        async with database.sessions["api"]() as session, session.begin():
            await enqueue_task(
                session,
                topic=TOPIC,
                key="rollback:one",
                payload={},
                deduplication_key="rollback",
            )
            raise RuntimeError("synthetic rollback")
    assert await execute(database, "api", "SELECT count(*) FROM outbox_message") == 0


async def test_worker_renew_and_stale_fencing_without_delete_permission(database):
    message = await enqueue(database)

    async def handler(session, payload):
        pass

    delivery = DurableTasks(database.sessions["worker"], handlers={TOPIC: handler})
    old, _ = await delivery.claim_execution(message)
    await delivery.renew(old)
    await execute(
        database,
        "migration",
        "UPDATE outbox_execution SET expires_at='-infinity'::timestamptz",
    )
    current, _ = await delivery.claim_execution(message)
    assert current.epoch == old.epoch + 1
    with pytest.raises(DeliveryLeaseLost):
        await delivery.renew(old)
    await delivery.release(old)
    assert (
        await execute(database, "api", "SELECT owner FROM outbox_execution")
        == current.owner
    )
    await delivery.release(current)
    assert await execute(database, "api", "SELECT count(*) FROM outbox_execution") == 1


async def test_new_tables_default_closed_and_grants_do_not_reconcile_old_roles(
    database,
):
    await execute(database, "migration", "CREATE TABLE unreviewed (id integer)")
    for role in ("api", "worker", "scheduler"):
        await denied(database, role, "SELECT * FROM public.unreviewed")
        await denied(database, role, "INSERT INTO public.unreviewed VALUES (1)")
    async with database.engines["migration"].begin() as connection:
        with pytest.raises(policy.PolicyError, match="unreviewed"):
            policy.template_grants(
                schema="public",
                principals=database.names,
                columns=await inventory(connection),
            )
    # A negative control: column-level REVOKE cannot cancel an old table grant.
    api = policy.identifier(database.names["api"])
    await execute(database, "migration", f"GRANT UPDATE ON alembic_version TO {api}")
    await execute(
        database,
        "migration",
        f"REVOKE UPDATE (version_num) ON alembic_version FROM {api}",
    )
    assert (
        await execute(
            database,
            "api",
            "UPDATE alembic_version SET version_num=version_num RETURNING version_num",
        )
        == "20260911_0003"
    )
    await execute(database, "migration", f"REVOKE UPDATE ON alembic_version FROM {api}")
    await denied(database, "api", "UPDATE alembic_version SET version_num=version_num")
