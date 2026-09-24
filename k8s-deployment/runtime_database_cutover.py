"""Pure, transaction-scoped bootstrap for reviewed runtime database identities.

Not a live connection, credential store or existing-role reconciler. Caller must
freeze and validate ownership/catalog/default-ACL inventories, stop old writers,
keep verified rollback materials, and prove no other consumers use old_logins.
The emitted SQL affects one current database except CREATE/NOLOGIN for named
roles. New names must not exist: CREATE ROLE deliberately has no IF NOT EXISTS.
"""
from __future__ import annotations

import re

from runtime_database_policy import PolicyError, ROLES, identifier


def cutover_sql(*, database, principals, passwords, old_logins, acl_creators,
                legacy_grantees, grant_statements, uuid_default=False):
    db = identifier(database)
    if set(principals) != ROLES or len(set(principals.values())) != 4:
        raise PolicyError("four distinct principals required")
    names = {role:identifier(name) for role,name in principals.items()}
    runtime = ROLES - {"migration"}
    if set(passwords) != runtime or len(set(passwords.values())) != 3 or any(
        not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{48}", value) for value in passwords.values()
    ):
        raise PolicyError("three fresh independent 192-bit hex passwords required")
    if not old_logins or set(old_logins) & set(principals.values()):
        raise PolicyError("old and new principals must not overlap")
    if not set(old_logins) <= set(legacy_grantees):
        raise PolicyError("all old logins must be revoked")
    if set(legacy_grantees) & set(principals.values()):
        raise PolicyError("cannot revoke new principals or owner")
    for name in (*old_logins, *legacy_grantees):
        identifier(name)
    if principals["migration"] not in acl_creators:
        raise PolicyError("migration creator defaults must be closed")
    for creator in acl_creators:
        if creator != "postgres":
            identifier(creator)
    # Additive grants must come from a reviewed compiler, not arbitrary SQL.
    if not grant_statements or any(not s.startswith("GRANT ") or ";" in s
                                   or not any(s.endswith(" TO " + names[r]) for r in runtime)
                                   for s in grant_statements):
        raise PolicyError("unreviewed grants")
    statements = ["BEGIN", "SET LOCAL lock_timeout='5s'", "SET LOCAL statement_timeout='30s'",
                  "SET LOCAL search_path=pg_catalog"]
    # Fail before any mutation on the wrong connection or unexpected membership.
    principal_literals = ",".join("'"+name+"'" for name in [principals["migration"], *old_logins])
    statements.append("DO $check$ BEGIN "
        f"IF current_database() <> '{database}' THEN RAISE EXCEPTION 'wrong cutover database'; END IF; "
        "IF EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
        f"WHERE r.rolname IN ({principal_literals})) THEN RAISE EXCEPTION 'unexpected role membership'; END IF; "
        "END $check$")
    for role in sorted(runtime):
        statements.append(f"CREATE ROLE {names[role]} LOGIN PASSWORD '{passwords[role]}' "
                          "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT")
    statements.append(f"REVOKE ALL ON DATABASE {db} FROM PUBLIC")
    for role in sorted(runtime):
        statements.append(f"GRANT CONNECT ON DATABASE {db} TO {names[role]}")
    # Do not retire old access until the new roles have passed real probes.
    for grantee in ("PUBLIC",):
        target = "PUBLIC" if grantee == "PUBLIC" else identifier(grantee)
        for objects in ("TABLES", "SEQUENCES", "FUNCTIONS"):
            statements.append(f'REVOKE ALL ON ALL {objects} IN SCHEMA "public" FROM {target}')
        statements.append(f'REVOKE ALL ON SCHEMA "public" FROM {target}')
        if grantee != "PUBLIC":
            statements.append(f"REVOKE ALL ON DATABASE {db} FROM {target}")
    for creator in sorted(set(acl_creators)):
        creator_sql = '"postgres"' if creator == "postgres" else identifier(creator)
        for scope in ("", ' IN SCHEMA "public"'):
            for objects in ("TABLES", "SEQUENCES", "FUNCTIONS", "TYPES"):
                for grantee in ("PUBLIC", *sorted(set(legacy_grantees))):
                    target = "PUBLIC" if grantee == "PUBLIC" else identifier(grantee)
                    statements.append(f"ALTER DEFAULT PRIVILEGES FOR ROLE {creator_sql}{scope} "
                                      f"REVOKE ALL ON {objects} FROM {target}")
    statements.extend(grant_statements)
    # Old installations own uuid-ossp functions under retired migration roles.
    # API/Worker inserts still use uuid_generate_v4() defaults; scheduler does not.
    if uuid_default:
        for role in ("api", "worker", "migration"):
            statements.append(f'GRANT EXECUTE ON FUNCTION "public"."uuid_generate_v4"() TO {names[role]}')
    statements.append("COMMIT")
    return ";\n".join(statements) + ";\n"


def retirement_sql(*, database, old_logins, legacy_grantees):
    """Only after successful new-identity probes and exact old-writer draining.

    NOLOGIN is not connection termination. Operator must independently confirm
    no old sessions remain, and refuse retirement if other databases use these
    logins. Never pass generic/administrative roles here.
    """
    db = identifier(database)
    if not old_logins or not set(old_logins) <= set(legacy_grantees):
        raise PolicyError("explicit old principals required")
    statements = ["BEGIN", "SET LOCAL lock_timeout='5s'", "SET LOCAL statement_timeout='30s'",
                  "SET LOCAL search_path=pg_catalog",
                  "DO $check$ BEGIN "
                  f"IF current_database() <> '{database}' THEN RAISE EXCEPTION 'wrong retirement database'; END IF; "
                  "END $check$"]
    for grantee in sorted(set(legacy_grantees)):
        target = identifier(grantee)
        for objects in ("TABLES", "SEQUENCES", "FUNCTIONS"):
            statements.append(f'REVOKE ALL ON ALL {objects} IN SCHEMA "public" FROM {target}')
        statements.append(f'REVOKE ALL ON SCHEMA "public" FROM {target}')
        statements.append(f"REVOKE ALL ON DATABASE {db} FROM {target}")
    for old in sorted(set(old_logins)):
        statements.append(f"ALTER ROLE {identifier(old)} NOLOGIN")
    statements.append("COMMIT")
    return ";\n".join(statements) + ";\n"


def upgrade_sql(*, database, principals, grant_statements):
    """Image-only upgrade after a migration: re-apply the reviewed additive grants
    to the EXISTING runtime identities. No role creation, no password, no default
    ACL change, no retirement. Same transaction layout as ``cutover_sql`` so the
    activation's inventory guard can be inserted after the search_path line.
    """
    db = identifier(database)
    if set(principals) != ROLES or len(set(principals.values())) != 4:
        raise PolicyError("four distinct principals required")
    names = {role: identifier(name) for role, name in principals.items()}
    runtime = ROLES - {"migration"}
    if not grant_statements or any(not s.startswith("GRANT ") or ";" in s
                                   or not any(s.endswith(" TO " + names[r]) for r in runtime)
                                   for s in grant_statements):
        raise PolicyError("unreviewed grants")
    runtime_literals = ",".join("'" + principals[r] + "'" for r in sorted(runtime))
    statements = ["BEGIN", "SET LOCAL lock_timeout='5s'", "SET LOCAL statement_timeout='30s'",
                  "SET LOCAL search_path=pg_catalog",
                  "DO $check$ BEGIN "
                  f"IF current_database() <> '{database}' THEN RAISE EXCEPTION 'wrong upgrade database'; END IF; "
                  f"IF (SELECT count(*) FROM pg_roles WHERE rolname IN ({runtime_literals})) <> 3 "
                  "THEN RAISE EXCEPTION 'runtime identities missing'; END IF; "
                  "IF EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
                  f"WHERE r.rolname IN ({runtime_literals})) THEN RAISE EXCEPTION 'unexpected role membership'; END IF; "
                  "END $check$"]
    for role in sorted(runtime):
        statements.append(f"GRANT CONNECT ON DATABASE {db} TO {names[role]}")
    statements.extend(grant_statements)
    statements.append("COMMIT")
    return ";\n".join(statements) + ";\n"

