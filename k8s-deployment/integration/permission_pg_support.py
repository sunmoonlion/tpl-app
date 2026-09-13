"""Shared disposable-only PostgreSQL test support; never a live provisioner."""

from __future__ import annotations

import os
import secrets
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import asyncpg
import pytest
import runtime_database_policy as policy
from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


class DisposableDatabase(SimpleNamespace):
    def __repr__(self):
        return "<DisposableDatabase credentials=redacted>"


def migrate(connection, backend):
    config = Config()
    config.set_main_option("script_location", str(backend / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    with EnvironmentContext(
        config,
        scripts,
        fn=lambda revision, context: scripts._upgrade_revs("head", revision),
    ) as environment:
        environment.configure(connection=connection)
        with environment.begin_transaction():
            environment.run_migrations()


async def inventory(connection):
    rows = (
        await connection.execute(
            text("""
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema='public' ORDER BY table_name, ordinal_position
    """)
        )
    ).all()
    result = {}
    for table, column in rows:
        result.setdefault(table, set()).add(column)
    return {table: frozenset(columns) for table, columns in result.items()}


@asynccontextmanager
async def provision_database(backend, compiler, *, scope="b7o", uuid_extension=False):
    assert scope in {"b7o", "b7p", "b7q"}
    assert os.environ.get("RUNTIME_POLICY_TEST_CONFIRM") == f"disposable-{scope}-only"
    url = make_url(os.environ["RUNTIME_POLICY_TEST_DATABASE_URL"])
    assert (url.host, url.port, url.database, url.username) == (
        "127.0.0.1",
        55439,
        "backlog_tests",
        "postgres",
    )
    token = scope + "_" + uuid.uuid4().hex
    names = {role: token + "_" + role for role in policy.ROLES}
    dbname, other = token + "_tests", token + "_other_tests"
    passwords = {role: secrets.token_hex(24) for role in policy.ROLES}
    admin = await asyncpg.connect(
        host=url.host,
        port=url.port,
        database=url.database,
        user=url.username,
        password=url.password,
        timeout=5,
        command_timeout=5,
    )
    created_roles, created_databases, engines = [], [], {}
    try:
        for role, name in sorted(names.items()):
            await admin.execute(
                f"CREATE ROLE {policy.identifier(name)} LOGIN PASSWORD '{passwords[role]}' "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
            )
            created_roles.append(name)
        for name in (dbname, other):
            owner = (
                policy.identifier(names["migration"])
                if name == dbname
                else '"postgres"'
            )
            await admin.execute(
                f"CREATE DATABASE {policy.identifier(name)} OWNER {owner}"
            )
            created_databases.append(name)
            await admin.execute(
                f"REVOKE ALL ON DATABASE {policy.identifier(name)} FROM PUBLIC"
            )
        for role in ("api", "worker", "scheduler"):
            await admin.execute(
                f"GRANT CONNECT ON DATABASE {policy.identifier(dbname)} TO {policy.identifier(names[role])}"
            )
        for role, name in names.items():
            engines[role] = create_async_engine(
                url.set(
                    drivername="postgresql+asyncpg",
                    database=dbname,
                    username=name,
                    password=passwords[role],
                ),
                poolclass=NullPool,
                hide_parameters=True,
                connect_args={"timeout": 5, "command_timeout": 5},
            )
        sessions = {
            role: async_sessionmaker(engine, expire_on_commit=False)
            for role, engine in engines.items()
        }
        async with engines["migration"].begin() as connection:
            # Fresh DB has no legacy roles, objects or default ACL history.
            await connection.execute(text("REVOKE ALL ON SCHEMA public FROM PUBLIC"))
            for objects in ("TABLES", "SEQUENCES", "FUNCTIONS"):
                await connection.execute(
                    text(
                        f"ALTER DEFAULT PRIVILEGES REVOKE ALL ON {objects} FROM PUBLIC"
                    )
                )
            if uuid_extension:
                await connection.execute(
                    text('CREATE EXTENSION "uuid-ossp" WITH SCHEMA public')
                )
            await connection.run_sync(lambda c: migrate(c, backend))
            columns = await inventory(connection)
            statements = compiler(schema="public", principals=names, columns=columns)
            for statement in statements:
                await connection.execute(text(statement))
        yield DisposableDatabase(
            sessions=sessions,
            engines=engines,
            names=names,
            admin=admin,
            database=dbname,
            other=other,
            passwords=passwords,
            url=url,
        )
    finally:
        for engine in engines.values():
            await engine.dispose()
        # No FORCE/CASCADE, terminate_backend, wildcards or DROP OWNED.
        for name in reversed(created_databases):
            await admin.execute(f"DROP DATABASE {policy.identifier(name)}")
        for name in reversed(created_roles):
            await admin.execute(f"DROP ROLE {policy.identifier(name)}")
        await admin.close()


async def execute(database, role, statement, params=None):
    async with database.sessions[role]() as session, session.begin():
        result = await session.execute(text(statement), params or {})
        return result.scalar_one_or_none() if result.returns_rows else None


async def denied(database, role, statement, params=None):
    with pytest.raises(DBAPIError) as caught:
        await execute(database, role, statement, params)
    assert caught.value.orig.sqlstate == "42501"
