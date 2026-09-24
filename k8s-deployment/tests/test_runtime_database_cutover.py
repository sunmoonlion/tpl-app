import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime_database_cutover as target
import runtime_database_policy as policy


class CutoverTest(unittest.TestCase):
    def args(self):
        principals = {r:"sample_"+r for r in policy.ROLES}
        return dict(database="sample_admin", principals=principals,
            passwords={r:str(i)*48 for i,r in enumerate(("api","worker","scheduler"),1)},
            old_logins=["sample_old"], acl_creators=["sample_migration","postgres"],
            legacy_grantees=["sample_old"],
            grant_statements=policy.template_grants(schema="public", principals=principals, columns=policy.TABLE_COLUMNS))

    def test_transaction_guard_fresh_roles_and_closed_defaults(self):
        sql = target.cutover_sql(**self.args())
        self.assertTrue(sql.startswith("BEGIN;"))
        self.assertTrue(sql.endswith("COMMIT;\n"))
        self.assertLess(sql.index("current_database()"),sql.index("CREATE ROLE"))
        self.assertEqual(sql.count("CREATE ROLE"),3)
        self.assertNotIn("IF NOT EXISTS",sql)
        self.assertNotIn('ALTER ROLE "sample_old" NOLOGIN',sql)
        self.assertNotIn('REVOKE ALL ON DATABASE "sample_admin" FROM "sample_old"',sql)
        self.assertIn('FOR ROLE "sample_migration" REVOKE ALL ON FUNCTIONS FROM PUBLIC',sql)
        self.assertIn('FOR ROLE "sample_migration" IN SCHEMA "public" REVOKE ALL ON TABLES FROM "sample_old"',sql)
        for forbidden in ("DROP ","DELETE ","TRUNCATE ","CASCADE","pg_terminate_backend"):
            self.assertNotIn(forbidden,sql)

    def test_independent_secret_and_scoped_identity_validation(self):
        cases = [dict(passwords={r:"a"*48 for r in ("api","worker","scheduler")}),
                 dict(old_logins=["sample_api"]),dict(legacy_grantees=["sample_migration"]),
                 dict(acl_creators=[]),dict(database="postgres"),
                 dict(grant_statements=['GRANT SELECT ON x TO "sample_api"; DROP DATABASE y'])]
        for mutation in cases:
            with self.subTest(mutation=list(mutation)),self.assertRaises(policy.PolicyError):
                target.cutover_sql(**(self.args()|mutation))

    def test_uuid_default_is_explicit_not_scheduler_access(self):
        sql = target.cutover_sql(**self.args(),uuid_default=True)
        grants = [s for s in sql.splitlines() if s.startswith("GRANT EXECUTE")]
        self.assertEqual(len(grants),3)
        self.assertFalse(any("scheduler" in s for s in grants))

    def test_retirement_is_separate_and_does_not_create_roles(self):
        sql = target.retirement_sql(database="sample_admin",old_logins=["sample_old"],legacy_grantees=["sample_old"])
        self.assertNotIn("CREATE ROLE",sql)
        self.assertIn('ALTER ROLE "sample_old" NOLOGIN',sql)
        self.assertIn('REVOKE ALL ON DATABASE "sample_admin" FROM "sample_old"',sql)
        self.assertNotIn("DROP ",sql)

    def test_upgrade_reapplies_reviewed_grants_without_creating_roles(self):
        args = self.args()
        sql = target.upgrade_sql(database=args["database"], principals=args["principals"],
                                 grant_statements=args["grant_statements"])
        self.assertTrue(sql.startswith("BEGIN;"))
        self.assertTrue(sql.endswith("COMMIT;\n"))
        self.assertIn("SET LOCAL search_path=pg_catalog;\n", sql)
        self.assertLess(sql.index("runtime identities missing"), sql.index("GRANT "))
        for forbidden in ("CREATE ROLE", "PASSWORD", "ALTER DEFAULT PRIVILEGES", "REVOKE", "NOLOGIN",
                          "DROP ", "DELETE ", "TRUNCATE ", "CASCADE"):
            self.assertNotIn(forbidden, sql)
        self.assertIn('GRANT CONNECT ON DATABASE "sample_admin" TO "sample_api"', sql)
        for bad in ([], ['GRANT SELECT ON x TO "sample_api"; DROP DATABASE y'], ['REVOKE ALL ON x FROM "sample_api"'],
                    ['GRANT SELECT ON x TO "sample_migration"']):
            with self.subTest(bad=bad), self.assertRaises(policy.PolicyError):
                target.upgrade_sql(database=args["database"], principals=args["principals"], grant_statements=bad)

