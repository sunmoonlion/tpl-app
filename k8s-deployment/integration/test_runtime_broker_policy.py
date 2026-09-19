"""Opt-in disposable Docker RabbitMQ only; never accepts an external broker URL."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
from uuid import uuid4

import asyncpg
import httpx
import pytest
from amqp.exceptions import AccessRefused, NotAllowed
from kombu import Connection, Exchange, Producer, Queue

DEPLOYMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEPLOYMENT))
from broker_test_support import auxiliary_service, select_auxiliary, select_backend
from runtime_broker_policy import broker_plan

BACKEND = select_backend(DEPLOYMENT, os.environ.get("BROKER_PERMISSION_TEST_BACKEND"))
AUXILIARY = select_auxiliary(os.environ.get("BROKER_PERMISSION_TEST_AUXILIARY", "none"))
sys.path.insert(0, str(BACKEND))
IMAGE = "sha256:ee10eb35bee296808f458c828ef7f581c15e4f18bcaf621742938b0897fcf718"


class BrokerInstance(SimpleNamespace):
    def __repr__(self):
        return "<disposable broker credentials redacted>"


def docker(*args, **kwargs):
    __tracebackhide__ = True
    try:
        result = subprocess.run(
            ["docker", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=40,
            check=False,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError("disposable Docker deadline exceeded") from None
    if result.returncode != 0:
        raise AssertionError("disposable Docker operation failed (output withheld)")
    return result.stdout.strip()


@pytest.fixture(scope="module")
def broker():
    assert os.environ.get("BROKER_PERMISSION_TEST_CONFIRM") == "disposable-b7s-only"
    suffix = uuid4().hex
    name = "luna-b7s-" + suffix
    admin = "admin-" + suffix
    password = secrets.token_urlsafe(24)
    cookie = secrets.token_hex(24)
    # Only random, fresh container; no mounts, shared networks or business secrets.
    container = docker(
        "run",
        "-d",
        "--name",
        name,
        "--label",
        "luna.disposable=b7s",
        "--memory=768m",
        "--cpus=2",
        "-p",
        "127.0.0.1::5672",
        "-p",
        "127.0.0.1::15672",
        "-e",
        "RABBITMQ_USERNAME",
        "-e",
        "RABBITMQ_PASSWORD",
        "-e",
        "RABBITMQ_ERL_COOKIE",
        "-e",
        "ERL_FLAGS=+S 2:2",
        IMAGE,
        env={
            **os.environ,
            "RABBITMQ_USERNAME": admin,
            "RABBITMQ_PASSWORD": password,
            "RABBITMQ_ERL_COOKIE": cookie,
        },
    )
    try:
        assert docker("inspect", container, "--format", "{{.Image}}") == IMAGE
        assert docker("inspect", container, "--format", "{{json .Mounts}}") == "[]"
        print(f"disposable RabbitMQ: {container}; image={IMAGE}; mounts=[]")
        amqp_address = docker("port", container, "5672").strip()
        http_address = docker("port", container, "15672").strip()
        assert amqp_address.startswith("127.0.0.1:")
        assert http_address.startswith("127.0.0.1:")
        # The image starts then stops a background broker during initialization.
        # Do not race management operations against that temporary first boot.
        deadline = time.monotonic() + 55
        while True:
            logs = docker("logs", container)
            final_boot = logs.partition("** Starting RabbitMQ **")[2]
            if "Server startup complete" in final_boot:
                break
            if time.monotonic() >= deadline:
                raise AssertionError("disposable broker final boot not reached")
            time.sleep(0.25)
        # Bitnami confines its bootstrap user to container localhost. Preserve
        # that restriction; create a fresh test-only manager through the CLI.
        docker("exec", container, "rabbitmqctl", "await_startup", "--timeout", "30")
        manager = "manager-" + suffix
        manager_password = secrets.token_urlsafe(24)
        docker("exec", container, "rabbitmqctl", "add_user", manager, manager_password)
        docker(
            "exec", container, "rabbitmqctl", "set_user_tags", manager, "administrator"
        )
        with httpx.Client(
            base_url=f"http://{http_address}/api/",
            auth=(manager, manager_password),
            timeout=3,
            trust_env=False,
        ) as client:
            deadline = time.monotonic() + 30
            while True:
                try:
                    status = client.get("overview").status_code
                except httpx.TransportError:
                    status = "transport-error"
                if status == 200:
                    break
                if time.monotonic() >= deadline:
                    listeners = docker(
                        "exec", container, "rabbitmq-diagnostics", "-q", "listeners"
                    )
                    users = docker(
                        "exec",
                        container,
                        "rabbitmqctl",
                        "list_users",
                        "--formatter=json",
                    )
                    logs = subprocess.run(
                        ["docker", "logs", container],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    diagnostic = (
                        (logs.stdout + logs.stderr)
                        .replace(password, "<redacted>")
                        .replace(manager_password, "<redacted>")
                        .replace(cookie, "<redacted>")
                    )
                    diagnostic = "\n".join(
                        line
                        for line in diagnostic.splitlines()
                        if "HTTP access denied" not in line
                    )
                    raise AssertionError(
                        f"disposable broker HTTP={status}; listeners={listeners}; users={users}; logs={diagnostic[-6000:]}"
                    )
                time.sleep(0.25)

            def api(method, path, body=None):
                result = client.request(method, path, json=body)
                assert result.is_success, (
                    f"broker management status {result.status_code}"
                )
                return result.json() if result.content else None

            @contextmanager
            def provision():
                ident = uuid4().hex
                vhost = "b7s-" + ident
                queue = "tasks." + ident
                names = {
                    role: f"{role}-{ident}" for role in ("api", "worker", "scheduler")
                }
                passwords = {role: secrets.token_urlsafe(24) for role in names}
                plan = broker_plan(vhost, queue, names)
                other = vhost + "-other"
                api("PUT", "vhosts/" + other, {})
                for role, user in names.items():
                    api(
                        "PUT",
                        "users/" + user,
                        {"password": passwords[role], "tags": []},
                    )
                api("POST", "definitions", plan)
                urls = {
                    role: f"amqp://{user}:{passwords[role]}@{amqp_address}/{vhost}"
                    for role, user in names.items()
                }

                def refresh_endpoints():
                    # Docker may reallocate ephemeral host ports after restart.
                    nonlocal amqp_address, http_address
                    new_amqp = docker("port", container, "5672").strip()
                    new_http = docker("port", container, "15672").strip()
                    assert new_amqp.startswith("127.0.0.1:")
                    assert new_http.startswith("127.0.0.1:")
                    print(
                        f"broker endpoints: {amqp_address}/{http_address} -> {new_amqp}/{new_http}"
                    )
                    amqp_address, http_address = new_amqp, new_http
                    client.base_url = f"http://{new_http}/api/"
                    for role, user in names.items():
                        urls[role] = (
                            f"amqp://{user}:{passwords[role]}@{new_amqp}/{vhost}"
                        )

                try:
                    yield BrokerInstance(
                        container=container,
                        refresh_endpoints=refresh_endpoints,
                        vhost=vhost,
                        queue=queue,
                        names=names,
                        urls=urls,
                        other=other,
                        api=api,
                        plan=plan,
                    )
                finally:
                    api("DELETE", "vhosts/" + vhost)
                    api("DELETE", "vhosts/" + other)
                    for user in names.values():
                        api("DELETE", "users/" + user)

            yield provision
    finally:
        # Exact random container ID and ownership label; no volume/image pruning.
        assert (
            docker(
                "inspect",
                container,
                "--format",
                '{{index .Config.Labels "luna.disposable"}}',
            )
            == "b7s"
        )
        docker("rm", "-f", container)
        assert (
            docker(
                "ps",
                "-a",
                "--no-trunc",
                "--filter",
                "id=" + container,
                "--format",
                "{{.ID}}",
            )
            == ""
        )
        print(f"disposable RabbitMQ removed: {container}")


@pytest.fixture
def instance(broker):
    with broker() as value:
        yield value


@contextmanager
def channel(instance, role):
    with (
        Connection(
            instance.urls[role],
            connect_timeout=3,
            transport_options={"confirm_publish": True},
        ) as connection,
        connection.channel() as value,
    ):
        yield value


@pytest.mark.parametrize("role", ["api", "scheduler"])
def test_old_auto_binding_requires_read_and_that_also_allows_consume(instance, role):
    row = next(
        row
        for row in instance.plan["permissions"]
        if row["user"] == instance.names[role]
    )
    permissions = {key: row[key] for key in ("configure", "write", "read")}
    permissions["configure"] = permissions["write"]
    instance.api("PUT", f"permissions/{instance.vhost}/{row['user']}", permissions)
    queue = Queue(
        instance.queue,
        Exchange(instance.queue, type="direct", durable=True),
        routing_key=instance.queue,
        durable=True,
    )
    with channel(instance, role) as ch, pytest.raises(AccessRefused):
        queue(ch).declare()  # declare succeeds; binding needs exchange read.
    permissions["read"] = permissions["write"]
    instance.api("PUT", f"permissions/{instance.vhost}/{row['user']}", permissions)
    with channel(instance, role) as ch:
        queue(ch).declare()
        Producer(ch).publish(
            {"synthetic": True},
            exchange=instance.queue,
            routing_key=instance.queue,
            serializer="json",
        )
        assert ch.basic_get(instance.queue) is not None  # proved unwanted consumption


@pytest.mark.parametrize("role", ["api", "scheduler"])
@pytest.mark.parametrize(
    "operation", ["get", "consume", "purge", "delete", "declare", "control", "other"]
)
def test_producer_forbidden_operations(instance, role, operation):
    if operation in {"control", "other"}:
        instance.api(
            "PUT",
            f"exchanges/{instance.vhost}/"
            + ("celery.pidbox" if operation == "control" else "other"),
            {"type": "fanout", "durable": False, "auto_delete": False, "arguments": {}},
        )
    with channel(instance, role) as ch, pytest.raises(AccessRefused):
        if operation == "get":
            ch.basic_get(instance.queue)
        elif operation == "consume":
            ch.basic_consume(instance.queue, consumer_tag="denied")
        elif operation == "purge":
            ch.queue_purge(instance.queue)
        elif operation == "delete":
            ch.queue_delete(instance.queue)
        elif operation == "declare":
            ch.queue_declare(instance.queue, durable=True)
        else:
            Producer(ch).publish(
                {},
                exchange="celery.pidbox" if operation == "control" else "other",
                routing_key=instance.queue,
            )


@pytest.mark.parametrize("role", ["api", "worker", "scheduler"])
def test_cross_vhost_is_denied(instance, role):
    url = instance.urls[role].rsplit("/", 1)[0] + "/" + instance.other
    with (
        pytest.raises((AccessRefused, NotAllowed)),
        Connection(url, connect_timeout=3) as connection,
    ):
        connection.connect()


def run(instance, role, *args, predeclared=True, extra=None):
    env = {
        **os.environ,
        "CELERY_BROKER_URL": instance.urls[role],
        "CELERY_QUEUE": instance.queue,
        "CELERY_RESULT_BACKEND": "",
        "CELERY_TASK_TOPOLOGY_PREDECLARED": str(predeclared).lower(),
        **(extra or {}),
    }
    return subprocess.run(
        [sys.executable, *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


@pytest.mark.parametrize("role", ["api", "worker", "scheduler"])
def test_actual_application_publish(instance, role):
    result = run(
        instance,
        role,
        "-c",
        "from app.infrastructure.messaging.celery_producer import CeleryProducer; CeleryProducer().dispatch_ping()",
    )
    assert result.returncode == 0, "application publication failed (output withheld)"
    with channel(instance, "worker") as ch:
        message = ch.basic_get(instance.queue)
        assert message is not None
        assert message.headers["task"] == "app.tasks.ping"
        ch.basic_ack(message.delivery_info["delivery_tag"])


@pytest.mark.parametrize("role", ["api", "scheduler"])
def test_actual_application_default_declaration_is_refused(instance, role):
    result = run(
        instance,
        role,
        "-c",
        "from app.infrastructure.messaging.celery_producer import CeleryProducer; CeleryProducer().dispatch_ping()",
        predeclared=False,
    )
    assert result.returncode != 0
    assert "AccessRefused" in result.stderr


def test_worker_cannot_delete_durable_topology(instance):
    with channel(instance, "worker") as ch, pytest.raises(AccessRefused):
        ch.queue_delete(instance.queue)
    with channel(instance, "worker") as ch, pytest.raises(AccessRefused):
        ch.exchange_delete(instance.queue)


@pytest.mark.parametrize("missing", ["queue", "exchange", "binding"])
def test_actual_publish_cannot_silently_drop_unroutable_task(instance, missing):
    if missing == "binding":
        bindings = instance.api(
            "GET", f"bindings/{instance.vhost}/e/{instance.queue}/q/{instance.queue}"
        )
        assert len(bindings) == 1
        instance.api(
            "DELETE",
            f"bindings/{instance.vhost}/e/{instance.queue}/q/{instance.queue}/"
            + quote(bindings[0]["properties_key"], safe=""),
        )
    else:
        instance.api("DELETE", f"{missing}s/{instance.vhost}/{instance.queue}")
    result = run(
        instance,
        "api",
        "-c",
        "from app.infrastructure.messaging.celery_producer import CeleryProducer; CeleryProducer().dispatch_ping()",
    )
    assert result.returncode != 0
    assert ("NotFound" if missing == "exchange" else "NO_ROUTE") in result.stderr


def test_actual_worker_default_control_events_and_readiness(instance):
    node = "b7s-" + uuid4().hex
    env = {
        **os.environ,
        "POD_NAME": node,
        "CELERY_BROKER_URL": instance.urls["worker"],
        "CELERY_QUEUE": instance.queue,
        "CELERY_RESULT_BACKEND": "",
        "CELERY_TASK_TOPOLOGY_PREDECLARED": "true",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "app.bootstrap.worker:celery_app",
            "worker",
            "--pool=prefork",
            "--concurrency=1",
            f"--hostname=celery@{node}",
            "--loglevel=WARNING",
        ],
        cwd=BACKEND,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            assert process.poll() is None, "worker exited"
            result = run(
                instance,
                "worker",
                "-m",
                "app.cli.worker_readiness",
                extra={"POD_NAME": node},
            )
            if result.returncode == 0:
                break
            assert time.monotonic() < deadline, "worker readiness not reached"
            time.sleep(0.1)
        # Default mingle/gossip/heartbeat are on; assert actual event/control topology.
        queues = instance.api("GET", "queues/" + instance.vhost)
        assert any(row["name"].startswith("celeryev.") for row in queues)
        assert any(row["name"] == f"celery@{node}.celery.pidbox" for row in queues)
        with channel(instance, "worker") as ch:
            _, _, consumers = ch.queue_declare(instance.queue, passive=True)
            assert consumers == 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_actual_scheduler_publishes_without_consuming(instance, tmp_path):
    schedule = str(tmp_path / "beat")
    env = {
        **os.environ,
        "CELERY_BROKER_URL": instance.urls["scheduler"],
        "CELERY_QUEUE": instance.queue,
        "CELERY_RESULT_BACKEND": "",
        "CELERY_TASK_TOPOLOGY_PREDECLARED": "true",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "app.bootstrap.scheduler:celery_app",
            "beat",
            "--loglevel=WARNING",
            "--max-interval=1",
            "--schedule",
            schedule,
        ],
        cwd=BACKEND,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while True:
            assert process.poll() is None
            with channel(instance, "worker") as ch:
                message = ch.basic_get(instance.queue)
                if message is not None:
                    assert message.headers["task"].startswith("app.tasks.")
                    ch.basic_ack(message.delivery_info["delivery_tag"])
                    break
            assert time.monotonic() < deadline, "Beat did not deliver an actual message"
            time.sleep(0.1)
        result = run(
            instance,
            "scheduler",
            "-m",
            "app.cli.scheduler_activity",
            "--schedule",
            schedule,
            "--max-age",
            "10",
        )
        assert result.returncode == 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_full_backend_gate_without_skips(instance, tmp_path):
    """Regression suite uses its own test vhost and fresh PG, not runtime ACLs."""
    suffix = uuid4().hex
    password = secrets.token_urlsafe(24)
    pg = docker(
        "run",
        "-d",
        "--pull=never",
        "--name",
        "luna-b7s-pg-" + suffix,
        "--label",
        "luna.disposable=b7s",
        "--memory=640m",
        "--cpus=2",
        "-p",
        "127.0.0.1::5432",
        "-e",
        "POSTGRESQL_PASSWORD",
        "-e",
        "POSTGRESQL_DATABASE=backlog_tests",
        "bitnami/postgresql:17.6.0-debian-12-r4",
        env={**os.environ, "POSTGRESQL_PASSWORD": password},
    )
    volumes = []
    try:
        mounts = json.loads(docker("inspect", pg, "--format", "{{json .Mounts}}"))
        assert all(row["Type"] == "volume" for row in mounts)
        volumes = [row["Name"] for row in mounts]
        print(
            f"disposable PostgreSQL: {pg}; image="
            + docker("inspect", pg, "--format", "{{.Image}}")
        )
        print(f"disposable PostgreSQL volumes: {volumes}")
        address = docker("port", pg, "5432")
        assert address.startswith("127.0.0.1:")

        async def wait_pg():
            deadline = time.monotonic() + 40
            while True:
                try:
                    connection = await asyncpg.connect(
                        host="127.0.0.1",
                        port=int(address.rsplit(":", 1)[1]),
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
                            "disposable regression PostgreSQL unavailable"
                        ) from None
                    await asyncio.sleep(0.2)

        asyncio.run(wait_pg())
        vhost = "luna_probe_tests"
        user = "regression-" + suffix
        broker_password = secrets.token_urlsafe(24)
        instance.api("PUT", "vhosts/" + vhost, {})
        instance.api("PUT", "users/" + user, {"password": broker_password, "tags": []})
        instance.api(
            "PUT",
            f"permissions/{vhost}/{user}",
            {"configure": ".*", "write": ".*", "read": ".*"},
        )
        broker_address = instance.urls["worker"].split("@", 1)[1].split("/", 1)[0]
        database_url = (
            f"postgresql+asyncpg://postgres:{password}@{address}/backlog_tests"
        )
        broker_url = f"amqp://{user}:{broker_password}@{broker_address}/{vhost}"
        report = tmp_path / "backend.xml"
        env = {
            **os.environ,
            "DELIVERY_TEST_DATABASE_URL": database_url,
            "AGENT_TEST_DATABASE_URL": database_url.replace(
                "postgresql+asyncpg://", "postgresql://", 1
            ),
            "CELERY_PROBE_TEST_BROKER_URL": broker_url,
            "WEB_INTERACTION_CONSUMER_VECTORS": str(
                DEPLOYMENT.parent / "contracts/web-interaction-v1.consumer-vectors.json"
            ),
        }
        # Do not let the calling shell opt the ordinary baseline suite into the
        # restricted mode: the dedicated permission tests above exercise it.
        env.pop("CELERY_TASK_TOPOLOGY_PREDECLARED", None)
        with auxiliary_service(AUXILIARY, docker) as (extra_env, extra_secrets):
            for key in ("ARTIFACT_TEST_S3_ENDPOINT", "AGENT_TEST_REDIS_URL"):
                env.pop(key, None)
            env.update(extra_env)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests",
                    "-q",
                    "-x",
                    f"--junitxml={report}",
                ],
                cwd=BACKEND,
                env=env,
                capture_output=True,
                text=True,
                timeout=240,
                check=False,
            )
            if result.returncode != 0:
                diagnostic = result.stdout + result.stderr
                for secret in (password, broker_password, *extra_secrets):
                    diagnostic = diagnostic.replace(secret, "<redacted>")
                raise AssertionError(diagnostic[-8000:])
        suites = list(ET.parse(report).getroot())
        assert sum(int(row.attrib["skipped"]) for row in suites) == 0
        assert (
            sum(
                int(row.attrib["failures"]) + int(row.attrib["errors"])
                for row in suites
            )
            == 0
        )
        print(
            f"{BACKEND.parent.name} full gate:", result.stdout.strip().splitlines()[-1]
        )
    finally:
        assert (
            docker(
                "inspect", pg, "--format", '{{index .Config.Labels "luna.disposable"}}'
            )
            == "b7s"
        )
        docker("rm", "-f", "-v", pg)
        assert (
            docker(
                "ps", "-a", "--no-trunc", "--filter", "id=" + pg, "--format", "{{.ID}}"
            )
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
        print(f"disposable PostgreSQL and volumes removed: {pg}")


@pytest.mark.parametrize("kind", ["s3", "redis"])
def test_auxiliary_support_startup_and_cleanup(broker, kind):
    # broker fixture enforces explicit disposable-test authorization first.
    with auxiliary_service(kind, docker) as (env, redactions):
        if kind == "s3":
            assert env == {"ARTIFACT_TEST_S3_ENDPOINT": "http://127.0.0.1:59039"}
        else:
            assert env["AGENT_TEST_REDIS_URL"].startswith("redis://:")
            assert "@127.0.0.1:" in env["AGENT_TEST_REDIS_URL"]
            assert len(redactions) == 1
