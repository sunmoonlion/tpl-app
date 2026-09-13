import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_broker_policy import broker_plan


class BrokerPolicyTest(unittest.TestCase):
    def plan(self, **overrides):
        values = {
            "vhost": "synthetic",
            "queue": "app.tasks",
            "principals": {
                "api": "test-api",
                "worker": "test-worker",
                "scheduler": "test-beat",
            },
        }
        values.update(overrides)
        return broker_plan(**values)

    def test_producer_has_only_exact_exchange_write(self):
        for row in self.plan()["permissions"][::2]:
            self.assertTrue(re.fullmatch(row["write"], "app.tasks"))
            for field in ("read", "configure"):
                self.assertFalse(re.fullmatch(row[field], "app.tasks"))
            self.assertFalse(re.fullmatch(row["write"], "appXtasks"))
            self.assertFalse(re.fullmatch(row["write"], "celery.pidbox"))

    def test_worker_cannot_configure_task_or_unknown_resources(self):
        row = self.plan()["permissions"][1]
        self.assertFalse(re.fullmatch(row["configure"], "app.tasks"))
        self.assertTrue(re.fullmatch(row["read"], "app.tasks"))
        for name in ("celeryevil", "celery.pidbox.extra", "amq.default", "other"):
            for field in ("read", "write", "configure"):
                self.assertFalse(re.fullmatch(row[field], name))

    def test_invalid_and_colliding_identifiers_fail_closed(self):
        for queue in (
            "celery.pidbox",
            "celeryev",
            "amq.default",
            "reply.foo",
            "a|b",
            "",
        ):
            with self.assertRaises(ValueError):
                self.plan(queue=queue)
        with self.assertRaises(ValueError):
            self.plan(principals={"api": "same", "worker": "same", "scheduler": "s"})

    def test_no_credentials_or_implicit_result_backend(self):
        plan = self.plan()
        self.assertNotIn("users", plan)
        self.assertEqual(len(plan["queues"]), 1)
        self.assertTrue(plan["queues"][0]["durable"])
        self.assertEqual(plan["bindings"][0]["routing_key"], "app.tasks")
