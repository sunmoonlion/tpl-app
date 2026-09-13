import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime_database_policy as policy


class PolicyTest(unittest.TestCase):
    def arguments(self):
        return {
            "schema": "public",
            "principals": {role: f"example_{role}" for role in policy.ROLES},
            "columns": copy.deepcopy(policy.TABLE_COLUMNS),
        }

    def test_exact_roles_and_no_wildcard_or_destructive_grants(self):
        args = self.arguments()
        original = copy.deepcopy(args)
        sql = policy.template_grants(**args)
        self.assertEqual(args, original)
        self.assertTrue(all(statement.startswith("GRANT ") for statement in sql))
        combined = "\n".join(sql)
        for forbidden in (
            "ALL TABLES",
            "ALL PRIVILEGES",
            "DELETE",
            "TRUNCATE",
            "PASSWORD",
            "DEFAULT PRIVILEGES",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertNotIn('TO "example_scheduler"', combined)
        self.assertNotIn('TO "example_migration"', combined)
        version = [statement for statement in sql if '"alembic_version"' in statement]
        self.assertEqual(len(version), 2)
        self.assertTrue(
            all(statement.startswith("GRANT SELECT ") for statement in version)
        )

    def test_api_outbox_updates_only_deduplication_key(self):
        sql = policy.template_grants(**self.arguments())
        updates = [
            s
            for s in sql
            if s.startswith("GRANT UPDATE")
            and s.endswith('TO "example_api"')
            and '"outbox_message"' in s
        ]
        self.assertEqual(
            updates,
            [
                'GRANT UPDATE ("deduplication_key") ON TABLE "public"."outbox_message" TO "example_api"'
            ],
        )

    def test_unknown_missing_or_changed_schema_fails_closed(self):
        for mutate in (
            lambda c: c.pop("alembic_version"),
            lambda c: c.update({"unreviewed": frozenset({"id"})}),
            lambda c: c.update(
                {"outbox_message": c["outbox_message"] | {"new_secret"}}
            ),
        ):
            args = self.arguments()
            mutate(args["columns"])
            with self.assertRaises(policy.PolicyError):
                policy.template_grants(**args)

    def test_shared_reserved_or_injected_principals_rejected(self):
        for name in (
            "example_api",
            "postgres",
            "public",
            "pg_admin",
            'x"; DROP ROLE y',
            "a" * 64,
        ):
            args = self.arguments()
            args["principals"]["worker"] = name
            with self.subTest(name=name), self.assertRaises(policy.PolicyError):
                policy.template_grants(**args)
        for key in ("api", "worker", "scheduler", "migration"):
            args = self.arguments()
            args["principals"].pop(key)
            with self.assertRaises(policy.PolicyError):
                policy.template_grants(**args)


if __name__ == "__main__":
    unittest.main()
