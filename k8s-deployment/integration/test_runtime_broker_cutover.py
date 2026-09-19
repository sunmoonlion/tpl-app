"""Opt-in test of the narrow definition merge on a disposable broker only."""
import copy
import secrets
from urllib.parse import quote

from amqp.exceptions import AccessRefused, NotAllowed
from kombu import Connection, Producer
import pytest

from test_runtime_broker_policy import broker as broker, instance as instance
from runtime_broker_cutover import merge_definitions, password_hash


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
