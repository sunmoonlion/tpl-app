"""Candidate PostgreSQL grants for the template's current schema only.

Pure compilation, not a live provisioner. Caller must establish fresh independent
roles, trusted ownership, no inherited/PUBLIC access and closed default ACLs.
Do not use these additive GRANTs to reconcile an existing overprivileged role.
Domain Apps require their own reviewed overlay; an unknown schema fails closed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

TABLE_COLUMNS = {
    "alembic_version": frozenset({"version_num"}),
    "auth_user": frozenset(
        {
            "id",
            "issuer",
            "subject",
            "username",
            "email",
            "display_name",
            "roles",
            "scopes",
            "created_at",
            "updated_at",
        }
    ),
    "outbox_message": frozenset(
        {
            "id",
            "topic",
            "aggregate_key",
            "deduplication_key",
            "payload",
            "headers",
            "status",
            "attempt_count",
            "available_at",
            "lease_owner",
            "lease_expires_at",
            "published_at",
            "last_error",
            "created_at",
            "updated_at",
        }
    ),
    "inbox_message": frozenset({"consumer", "message_id", "processed_at"}),
    "outbox_dead_letter": frozenset(
        {"message_id", "error_code", "failed_at", "replayed_at"}
    ),
    "outbox_execution": frozenset(
        {"resource_key", "message_id", "owner", "epoch", "expires_at"}
    ),
}
INTENT_COLUMNS = (
    "id",
    "topic",
    "aggregate_key",
    "deduplication_key",
    "payload",
    "headers",
    "available_at",
)
AUTH_INSERT_COLUMNS = (
    "id",
    "issuer",
    "subject",
    "username",
    "email",
    "display_name",
    "roles",
    "scopes",
)
AUTH_UPDATE_COLUMNS = (
    "username",
    "email",
    "display_name",
    "roles",
    "scopes",
    "updated_at",
)
ROLES = frozenset({"api", "worker", "scheduler", "migration"})


class PolicyError(ValueError):
    pass


def identifier(value: str) -> str:
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value)
        or value.startswith("pg_")
        or value in {"postgres", "public"}
    ):
        raise PolicyError("invalid policy identifier")
    return f'"{value}"'


def template_grants(
    *, schema: str, principals: Mapping[str, str], columns: Mapping[str, frozenset[str]]
) -> tuple[str, ...]:
    """Compile exact grants after matching the migrated table/column inventory.

    Intentionally no connection, default grants, ownership changes, password or
    wildcard privileges. Scheduler gets no schema/table grants; its CONNECT is
    supplied by the external identity bootstrap. Migration already owns objects.
    """
    schema_sql = '"public"' if schema == "public" else identifier(schema)
    if set(principals) != ROLES or len(set(principals.values())) != len(ROLES):
        raise PolicyError("four independent principals required")
    roles = {role: identifier(name) for role, name in principals.items()}
    if dict(columns) != TABLE_COLUMNS:
        raise PolicyError("unreviewed table or column inventory")

    statements = []

    def grant(role, table, privilege, names=()):
        columns_sql = (
            " (" + ", ".join(identifier(name) for name in names) + ")" if names else ""
        )
        statements.append(
            f"GRANT {privilege}{columns_sql} ON TABLE {schema_sql}.{identifier(table)} TO {roles[role]}"
        )

    for role in ("api", "worker"):
        statements.append(f"GRANT USAGE ON SCHEMA {schema_sql} TO {roles[role]}")
        for table in TABLE_COLUMNS:
            if role == "worker" and table == "auth_user":
                continue
            grant(role, table, "SELECT")

    grant("api", "auth_user", "INSERT", AUTH_INSERT_COLUMNS)
    grant("api", "auth_user", "UPDATE", AUTH_UPDATE_COLUMNS)
    grant("api", "outbox_message", "INSERT", INTENT_COLUMNS)
    # enqueue's ON CONFLICT performs a no-op update of this one column.
    grant("api", "outbox_message", "UPDATE", ("deduplication_key",))
    grant("worker", "outbox_message", "INSERT", INTENT_COLUMNS)
    for table in ("outbox_message", "outbox_dead_letter", "outbox_execution"):
        grant("worker", table, "UPDATE")
    for table in ("inbox_message", "outbox_dead_letter", "outbox_execution"):
        grant("worker", table, "INSERT")
    return tuple(statements)
