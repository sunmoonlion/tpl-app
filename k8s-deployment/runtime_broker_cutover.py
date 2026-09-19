"""Pure narrow merge into shared broker definitions; no live import/restart.

Keep non-target resources and users byte-for-byte at the JSON value level.
New users must be freshly named, or already identical for an exact retry.
Retirement removes only explicitly named users' permissions on this vhost;
it never deletes users, vhosts, queues, exchanges, bindings or messages.
"""
import base64
import copy
import hashlib
import re
from urllib.parse import quote

from runtime_broker_policy import broker_plan


def password_hash(password, salt):
    if not isinstance(password,str) or not re.fullmatch(r"[0-9a-f]{48}",password) or len(salt)!=4:
        raise ValueError("fresh random password and four-byte salt required")
    return base64.b64encode(salt+hashlib.sha256(salt+password.encode()).digest()).decode()


def merge_definitions(existing, *, vhost, queue, principals, users, retire_users=()):
    plan = broker_plan(vhost,queue,principals)
    names = set(principals.values())
    if len(users)!=3 or {u.get("name") for u in users}!=names or names & set(retire_users):
        raise ValueError("wrong cutover users")
    for user in users:
        if (set(user)!={"name","password_hash","hashing_algorithm","tags"}
                or user["hashing_algorithm"]!="rabbit_password_hashing_sha256" or user["tags"]!=[]
                or len(base64.b64decode(user["password_hash"],validate=True))!=36):
            raise ValueError("unreviewed user definition")
    if any(not re.fullmatch(r"[a-z][a-z0-9_.-]{0,100}",name) for name in retire_users):
        raise ValueError("unsafe retired user")
    result = copy.deepcopy(existing)
    plan["users"] = users
    keys = {"vhosts":("name",),"users":("name",),"permissions":("vhost","user"),
            "queues":("vhost","name"),"exchanges":("vhost","name"),
            "bindings":("vhost","source","destination","destination_type","routing_key")}
    for kind, incoming in plan.items():
        rows = result.setdefault(kind,[])
        if not isinstance(rows,list):
            raise ValueError("invalid definitions collection")
        def identity(row):
            return tuple(row[k] for k in keys[kind])
        seen = [identity(row) for row in rows]
        if len(set(seen))!=len(seen):
            raise ValueError("duplicate existing definition identity")
        for row in incoming:
            key = identity(row)
            if key not in seen:
                rows.append(copy.deepcopy(row))
                seen.append(key)
                continue
            actual = rows[seen.index(key)]
            # Compare declared fields only; preserve non-target/extra metadata.
            expected = row
            if kind=="queues" and actual.get("arguments")=={"x-queue-type":"classic"}:
                expected = row | {"arguments":{"x-queue-type":"classic"}}
            if any(actual.get(field)!=value for field,value in expected.items()):
                raise ValueError("existing target differs from reviewed plan")
    result["permissions"] = [row for row in result["permissions"]
                              if not(row["vhost"]==vhost and row["user"] in retire_users)]
    return result


def preparation_plan(startup, live, *, vhost, queue, principals, users):
    """Fresh users + exact permissions only; existing live topology must match.

    Startup is a merge with all non-target values preserved. Live execution is
    six narrowly addressed PUTs, never a whole-cluster definitions import.
    Caller owns compare-and-swap persistence, exclusive reservation, backups,
    rechecking fresh names, auth probes and stopping on any uncertain result.
    """
    names = set(principals.values())
    for current in (startup, live):
        if any(row.get("name") in names for row in current.get("users", [])) or any(
                row.get("user") in names for row in current.get("permissions", [])):
            raise ValueError("cutover user already exists; no overwrite or automatic retry")
    args = dict(vhost=vhost, queue=queue, principals=principals, users=users)
    merged_live = merge_definitions(live, **args)
    for kind in ("vhosts", "queues", "exchanges", "bindings"):
        if merged_live[kind] != live.get(kind, []):
            raise ValueError("live task topology must already match the reviewed plan")
    merged_startup = merge_definitions(startup, **args)
    operations = []
    for user in users:
        operations.append({"method": "PUT", "path": "users/" + quote(user["name"], safe=""),
                           "body": {key: value for key, value in user.items() if key != "name"}})
    for permission in broker_plan(vhost, queue, principals)["permissions"]:
        operations.append({"method": "PUT", "path": "permissions/" + quote(vhost, safe="") + "/" + quote(permission["user"], safe=""),
                           "body": {key: permission[key] for key in ("configure", "write", "read")}})
    return {"startup": merged_startup, "operations": operations}
