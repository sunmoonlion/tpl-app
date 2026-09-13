"""Test-only handler assembly; real storage, Celery tasks, leases and ACKs.

Coordination files live in a pytest-owned directory, not in a business workspace.
No extra database grants/tables or shortened production lease are required.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.application.services.durable_tasks import enqueue_task
from app.bootstrap.worker import celery_app
from app.tasks import durable_delivery
from sqlalchemy import text

assert os.environ.get("JOINT_RUNTIME_TEST_CONFIRM") == "disposable-b7u-only"
assert celery_app.conf.task_acks_late is True
CONTROL = Path(os.environ["JOINT_RUNTIME_TEST_CONTROL"])
assert CONTROL.is_absolute() and CONTROL.is_dir()
TOPIC = "test.joint.runtime.v1"
RECEIPT = "test.joint.receipt.v1"


async def handler(session, payload):
    # The committed follow-on intent is a transactional effect, not a log receipt.
    identity = (await session.execute(text("SELECT current_user"))).scalar_one()
    await enqueue_task(
        session,
        topic=RECEIPT,
        key=payload["key"],
        payload={"worker_identity": identity},
        deduplication_key="effect:" + payload["key"],
    )
    if payload.get("fail") and not (CONTROL / "release-failure").exists():
        raise RuntimeError("synthetic-joint-rollback")
    if payload.get("crash") and not (CONTROL / "release-crash").exists():
        (CONTROL / "transaction-open").touch()
        # Parent kills this isolated process group while the transaction is open.
        async with asyncio.timeout(30):
            while not (CONTROL / "release-crash").exists():
                await asyncio.sleep(0.05)


async def receipt(session, payload):
    pass


durable_delivery.get_delivery_handlers = lambda: {TOPIC: handler, RECEIPT: receipt}
