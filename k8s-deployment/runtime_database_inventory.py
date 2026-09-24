"""Fail-closed inventory preconditions for fresh-role database activation.

Pure validation; not a connection or proof of quiescence between observations.
The caller must collect under a maintenance window and recheck immediately
before executing the transaction. Domain table/column validation stays in the
reviewed domain grant compiler, never inferred from this inventory.
"""
from runtime_database_policy import PolicyError, ROLES, identifier


def validate_bootstrap(inventory, *, database, head, principals, old_login,
                       legacy_grantees, function_owners, reviewed_functions=None, require_quiescent=True):
    identifier(database)
    if set(principals) != ROLES or len(set(principals.values())) != 4:
        raise PolicyError("four independent identities required")
    for name in (*principals.values(), old_login, *legacy_grantees):
        identifier(name)
    for name in function_owners:
        if name != "postgres":
            identifier(name)
    migration = principals["migration"]
    if old_login not in legacy_grantees or set(legacy_grantees) & set(principals.values()):
        raise PolicyError("legacy identity scope mismatch")
    if inventory["database"] != database or inventory["owner"] != migration or inventory["revisions"] != [head]:
        raise PolicyError("database owner or migration head mismatch")
    if inventory["schemas"] != [{"name": "public", "owner": migration}]:
        raise PolicyError("unreviewed schema ownership")
    roles = {row["name"]: row for row in inventory["roles"]}
    if len(roles) != len(inventory["roles"]) or set(roles) != {old_login, migration}:
        raise PolicyError("missing old identity or new identity already exists")
    for role in roles.values():
        if not role["login"] or any(role[key] for key in ("super", "create_db", "create_role", "replication", "bypass_rls")):
            raise PolicyError("unexpected legacy role attributes")
    if inventory["memberships"] or inventory["column_acl_count"] or inventory["event_trigger_count"]:
        raise PolicyError("unreviewed membership, column ACL or event trigger")
    for row in inventory["relations"]:
        if row["owner"] != migration or row["kind"] != "r" or row["rls"]:
            raise PolicyError("unreviewed relation ownership, kind or RLS")
    allowed_grantees = {migration, *legacy_grantees, "PUBLIC", "postgres"}
    for row in inventory["acl_grantees"]:
        if row["grantee"] not in allowed_grantees:
            raise PolicyError("foreign explicit grantee would be affected")
    creators = {migration}
    for row in inventory["default_acl"]:
        if row["creator"] not in {migration, *function_owners, "postgres"} or row["schema"] not in {"public", "<global>"}:
            raise PolicyError("unreviewed default ACL creator or schema")
        creators.add(row["creator"])
        for value in row["acl"]:
            grantee = value.split("=", 1)[0]
            if grantee not in legacy_grantees and grantee not in {"", row["creator"]}:
                raise PolicyError("unreviewed default ACL grantee")
    for row in inventory["functions"]:
        extension_function = row["extension"] == "uuid-ossp" and row["owner"] in {migration, *function_owners}
        reviewed_function = (row["extension"] is None and row["owner"] == migration
                             and row.get("definition") == (reviewed_functions or {}).get(row["name"])
                             and row.get("definition") is not None)
        if row["security_definer"] or not (extension_function or reviewed_function):
            raise PolicyError("unreviewed function authority")
    for row in inventory["activity"]:
        if row["user"] != "postgres" and (require_quiescent or row["user"] not in {old_login, migration}
                                           or row["database"] != database):
            raise PolicyError("old or unknown database clients remain")
    return {"acl_creators": sorted(creators), "legacy_grantees": sorted(legacy_grantees)}


def validate_upgrade(inventory, *, database, head, principals, old_login,
                     legacy_grantees, function_owners, reviewed_functions=None):
    """Same reviewed authority as ``validate_bootstrap`` for an App whose three
    runtime identities already exist (image-only upgrade after a new migration).

    Differences, and only these: the runtime roles must already exist with the
    bootstrap attributes, and explicit grantees may include them. Everything
    else (owner, schema, relations, defaults, functions, quiescence) is as strict
    as the first activation. Returns the same creators/legacy summary.
    """
    identifier(database)
    if set(principals) != ROLES or len(set(principals.values())) != 4:
        raise PolicyError("four independent identities required")
    for name in (*principals.values(), old_login, *legacy_grantees):
        identifier(name)
    for name in function_owners:
        if name != "postgres":
            identifier(name)
    migration = principals["migration"]
    runtime = {principals[r] for r in ROLES - {"migration"}}
    if old_login not in legacy_grantees or set(legacy_grantees) & set(principals.values()):
        raise PolicyError("legacy identity scope mismatch")
    if inventory["database"] != database or inventory["owner"] != migration or inventory["revisions"] != [head]:
        raise PolicyError("database owner or migration head mismatch")
    if inventory["schemas"] != [{"name": "public", "owner": migration}]:
        raise PolicyError("unreviewed schema ownership")
    roles = {row["name"]: row for row in inventory["roles"]}
    if len(roles) != len(inventory["roles"]) or set(roles) != {old_login, migration, *runtime}:
        raise PolicyError("runtime identities must already exist for an upgrade")
    for role in roles.values():
        if not role["login"] or any(role[key] for key in ("super", "create_db", "create_role", "replication", "bypass_rls")):
            raise PolicyError("unexpected role attributes")
        if role["name"] in runtime and role.get("inherit", False):
            raise PolicyError("runtime identities must not inherit")
    if inventory["memberships"] or inventory["event_trigger_count"]:
        raise PolicyError("unreviewed membership or event trigger")
    for row in inventory["relations"]:
        if row["owner"] != migration or row["kind"] != "r" or row["rls"]:
            raise PolicyError("unreviewed relation ownership, kind or RLS")
    allowed_grantees = {migration, *legacy_grantees, *runtime, "PUBLIC", "postgres"}
    for row in inventory["acl_grantees"]:
        if row["grantee"] not in allowed_grantees:
            raise PolicyError("foreign explicit grantee would be affected")
    for row in inventory.get("column_acl", []):
        grantees = {value.split("=", 1)[0] for value in row["acl"]}
        if not grantees <= runtime:
            raise PolicyError("unreviewed column ACL grantee")
    creators = {migration}
    for row in inventory["default_acl"]:
        if row["creator"] not in {migration, *function_owners, "postgres"} or row["schema"] not in {"public", "<global>"}:
            raise PolicyError("unreviewed default ACL creator or schema")
        creators.add(row["creator"])
        for value in row["acl"]:
            grantee = value.split("=", 1)[0]
            if grantee not in legacy_grantees and grantee not in {"", row["creator"]}:
                raise PolicyError("unreviewed default ACL grantee")
    for row in inventory["functions"]:
        extension_function = row["extension"] == "uuid-ossp" and row["owner"] in {migration, *function_owners}
        reviewed_function = (row["extension"] is None and row["owner"] == migration
                             and row.get("definition") == (reviewed_functions or {}).get(row["name"])
                             and row.get("definition") is not None)
        if row["security_definer"] or not (extension_function or reviewed_function):
            raise PolicyError("unreviewed function authority")
    for row in inventory["activity"]:
        if row["user"] != "postgres":
            raise PolicyError("database clients remain; stop the App first")
    return {"acl_creators": sorted(creators), "legacy_grantees": sorted(legacy_grantees)}

