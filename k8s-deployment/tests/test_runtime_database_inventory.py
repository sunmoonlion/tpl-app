import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_database_inventory import validate_bootstrap, PolicyError


class InventoryTest(unittest.TestCase):
    def fixture(self):
        principals = {r: "sample_" + r for r in ("api", "worker", "scheduler", "migration")}
        args = dict(database="sample_db", head="head-id", principals=principals, old_login="sample_old",
                    legacy_grantees={"sample_old"}, function_owners={"sample_previous_migration"})
        inventory = {"database": "sample_db", "owner": "sample_migration", "revisions": ["head-id"],
            "schemas": [{"name": "public", "owner": "sample_migration"}],
            "roles": [{"name": name, "login": True, "super": False, "create_db": False, "create_role": False,
                       "replication": False, "bypass_rls": False} for name in ("sample_old", "sample_migration")],
            "memberships": [], "column_acl_count": 0, "event_trigger_count": 0,
            "relations": [{"owner": "sample_migration", "kind": "r", "rls": False}], "acl_grantees": [],
            "default_acl": [], "functions": [], "activity": []}
        return inventory, args

    def test_reviewed_quiescent_inventory(self):
        inventory, args = self.fixture()
        self.assertEqual(validate_bootstrap(inventory, **args),
                         {"acl_creators": ["sample_migration"], "legacy_grantees": ["sample_old"]})

    def test_all_unreviewed_authority_fails_closed(self):
        for field, value in (("owner", "foreign"), ("revisions", ["old"]), ("schemas", []),
                             ("roles", []), ("memberships", [{}]), ("column_acl_count", 1), ("event_trigger_count", 1),
                             ("relations", [{"owner": "foreign", "kind": "r", "rls": False}]),
                             ("acl_grantees", [{"grantee": "foreign"}]),
                             ("functions", [{"owner": "sample_migration", "security_definer": True, "extension": "uuid-ossp"}]),
                             ("activity", [{"user": "sample_old", "database": "sample_db"}])):
            inventory, args = self.fixture()
            inventory[field] = value
            with self.subTest(field=field), self.assertRaises(PolicyError):
                validate_bootstrap(inventory, **args)

    def test_plan_can_observe_known_old_clients_not_cross_database_use(self):
        inventory, args = self.fixture()
        inventory["activity"] = [{"user": "sample_old", "database": "sample_db"}]
        validate_bootstrap(inventory, **args, require_quiescent=False)
        inventory["activity"][0]["database"] = "foreign_db"
        with self.assertRaises(PolicyError):
            validate_bootstrap(inventory, **args, require_quiescent=False)

    def test_existing_fresh_role_and_privileged_migration_rejected(self):
        inventory, args = self.fixture()
        inventory["roles"].append(inventory["roles"][0] | {"name": "sample_api"})
        with self.assertRaises(PolicyError):
            validate_bootstrap(inventory, **args)

    def test_reviewed_extension_owner_and_exact_native_function_only(self):
        inventory, args = self.fixture()
        args["function_owners"].add("postgres")
        extension = {"name": "uuid_generate_v4", "owner": "postgres",
                     "extension": "uuid-ossp", "security_definer": False}
        native = {"name": "immutable_guard", "owner": "sample_migration", "extension": None,
                  "security_definer": False, "definition": "reviewed definition"}
        args["reviewed_functions"] = {"immutable_guard": "reviewed definition"}
        inventory["functions"] = [extension, native]
        validate_bootstrap(inventory, **args)
        for changed in ({"definition": "different body"}, {"security_definer": True},
                        {"owner": "postgres"}, {"name": "unreviewed_function"}):
            inventory["functions"] = [extension, native | changed]
            with self.subTest(changed=changed), self.assertRaises(PolicyError):
                validate_bootstrap(inventory, **args)
        inventory, args = self.fixture()
        inventory["roles"][1]["super"] = True
        with self.assertRaises(PolicyError):
            validate_bootstrap(inventory, **args)
