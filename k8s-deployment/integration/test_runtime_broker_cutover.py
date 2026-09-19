"""Opt-in test of the narrow definition merge on a disposable broker only."""
import copy
import secrets
from urllib.parse import quote

from amqp.exceptions import AccessRefused, NotAllowed
from kombu import Connection, Producer
import pytest

from test_runtime_broker_policy import broker as broker, instance as instance
from runtime_broker_cutover import merge_definitions, password_hash, preparation_plan


def test_merge_real_hash_authentication_and_scoped_retirement(instance):
    existing = instance.api("GET", "definitions")
    baseline = copy.deepcopy(existing)
    names = {role:old+"-v2" for role,old in instance.names.items()}
    passwords = {role:secrets.token_hex(24) for role in names}
    users = [{"name":names[r],"tags":[],"hashing_algorithm":"rabbit_password_hashing_sha256",
              "password_hash":password_hash(passwords[r],secrets.token_bytes(4))} for r in names]
    args = dict(vhost=instance.vhost,queue=instance.queue,principals=names,users=users)
    merged = merge_definitions(existing,**args)
    assert existing == baseline
    for kind,rows in baseline.items():
        if isinstance(rows,list):
            assert all(row in merged[kind] for row in rows)
    instance.api("POST","definitions",merged)
    # Use the known fixture host/port but never its credentials for the new users.
    from urllib.parse import urlsplit
    endpoint = urlsplit(instance.urls["api"])
    def connection(role):
        return Connection(f"amqp://{names[role]}:{passwords[role]}@{endpoint.hostname}:{endpoint.port}/{instance.vhost}",connect_timeout=3)
    with connection("api") as conn:
        conn.ensure_connection(max_retries=0)
        Producer(conn.channel()).publish({"synthetic":"cutover"},exchange=instance.queue,
                                         routing_key=instance.queue,serializer="json",delivery_mode=2)
    for role in ("api","scheduler"):
        with connection(role) as conn:
            conn.ensure_connection(max_retries=0)
            with pytest.raises(AccessRefused):
                conn.channel().basic_get(instance.queue)
    with connection("worker") as conn:
        conn.ensure_connection(max_retries=0)
        channel = conn.channel()
        message = channel.basic_get(instance.queue)
        assert message is not None
        channel.basic_ack(message.delivery_info["delivery_tag"])
    old = instance.names["api"]
    retired = merge_definitions(merged,**args,retire_users=(old,))
    # Definition import is additive: a removed entry alone does not revoke live
    # access. The future operator must also delete this exact permission pair.
    instance.api("POST","definitions",retired)
    still_present = instance.api("GET",f"permissions/{instance.vhost}/{old}")
    assert still_present["user"] == old
    instance.api("DELETE",f"permissions/{instance.vhost}/{old}")
    with pytest.raises(NotAllowed):
        with Connection(instance.urls["api"],connect_timeout=3) as conn:
            conn.ensure_connection(max_retries=0)
    for permission in retired["permissions"]:
        actual = instance.api("GET",f"permissions/{quote(permission['vhost'],safe='')}/{quote(permission['user'],safe='')}")
        assert all(actual[k]==v for k,v in permission.items())


def test_narrow_preparation_puts_and_authentication(instance):
    existing = instance.api("GET", "definitions")
    names = {role: old + "-prepared" for role, old in instance.names.items()}
    passwords = {role: secrets.token_hex(24) for role in names}
    users = [{"name": names[r], "tags": [], "hashing_algorithm": "rabbit_password_hashing_sha256",
              "password_hash": password_hash(passwords[r], secrets.token_bytes(4))} for r in names]
    plan = preparation_plan(existing, existing, vhost=instance.vhost, queue=instance.queue,
                            principals=names, users=users)
    for operation in plan["operations"]:
        instance.api(operation["method"], operation["path"], operation["body"])
    after = instance.api("GET", "definitions")
    for kind, before in existing.items():
        if isinstance(before, list):
            assert all(row in after[kind] for row in before), kind
    from urllib.parse import urlsplit
    endpoint = urlsplit(instance.urls["api"])
    from runtime_broker_probe import verify_logins
    proof = verify_logins({r: f"amqp://{names[r]}:{passwords[r]}@{endpoint.hostname}:{endpoint.port}/{instance.vhost}"
                           for r in names}, "/")
    assert proof == {"authenticated_roles": 3, "foreign_vhost_denied": 3, "messages_touched": False}
    for role in names:
        with Connection(f"amqp://{names[role]}:{passwords[role]}@{endpoint.hostname}:{endpoint.port}/{instance.vhost}",
                        connect_timeout=3) as connection:
            connection.ensure_connection(max_retries=0)
            if role != "worker":
                with pytest.raises(AccessRefused):
                    connection.channel().basic_get(instance.queue)
    # The old users still authenticate; preparation must not retire them.
    with Connection(instance.urls["worker"], connect_timeout=3) as old:
        old.ensure_connection(max_retries=0)
