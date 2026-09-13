"""Pure AMQP ACL/topology candidate, not a live provisioner or credential store.

Requires CELERY_TASK_TOPOLOGY_PREDECLARED=true and no result backend.
Worker pidbox is a trusted control plane, not per-command authorization.
"""

from __future__ import annotations

import re


def broker_plan(vhost: str, queue: str, principals: dict[str, str]) -> dict:
    for value in (vhost, queue, *principals.values()):
        if not isinstance(value, str) or not re.fullmatch(
            r"[a-z][a-z0-9_.-]{0,100}", value
        ):
            raise ValueError("unsafe broker identifier")
    if (
        set(principals) != {"api", "worker", "scheduler"}
        or len(set(principals.values())) != 3
    ):
        raise ValueError("three distinct runtime principals required")
    if queue.startswith(("celery", "reply.", "amq.")):
        raise ValueError("task queue overlaps reserved control namespace")
    task = re.escape(queue)
    uid = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    control = (
        r"celery\.pidbox|reply\.celery\.pidbox|"
        r"celery@[a-z0-9][a-z0-9-]*\.celery\.pidbox|"
        + uid
        + r"\.reply\.celery\.pidbox|celeryev|celeryev\."
        + uid
    )
    permissions = []
    for role in ("api", "worker", "scheduler"):
        worker = role == "worker"
        permissions.append(
            {
                "user": principals[role],
                "vhost": vhost,
                "configure": f"^({control})$" if worker else "^$",
                "write": f"^({task}|{control})$" if worker else f"^{task}$",
                "read": f"^({task}|{control})$" if worker else "^$",
            }
        )
    return {
        "vhosts": [{"name": vhost}],
        "permissions": permissions,
        "queues": [
            {
                "name": queue,
                "vhost": vhost,
                "durable": True,
                "auto_delete": False,
                "arguments": {},
            }
        ],
        "exchanges": [
            {
                "name": queue,
                "vhost": vhost,
                "type": "direct",
                "durable": True,
                "auto_delete": False,
                "internal": False,
                "arguments": {},
            }
        ],
        "bindings": [
            {
                "source": queue,
                "vhost": vhost,
                "destination": queue,
                "destination_type": "queue",
                "routing_key": queue,
                "arguments": {},
            }
        ],
    }
