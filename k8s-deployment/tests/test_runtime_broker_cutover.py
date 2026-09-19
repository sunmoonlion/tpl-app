import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import runtime_broker_cutover as target


class BrokerCutoverTest(unittest.TestCase):
    def args(self):
        names = {r:"sample-"+r for r in ("api","worker","scheduler")}
        return dict(vhost="sample-dev",queue="sample.tasks",principals=names,
                    users=[{"name":name,"tags":[],"hashing_algorithm":"rabbit_password_hashing_sha256",
                            "password_hash":target.password_hash(str(i)*48,b"salt")}
                           for i,name in enumerate(names.values(),1)])

    def existing(self):
        return {"custom":{"retained":True},"users":[{"name":"old","opaque":"retained"}],
                "permissions":[{"vhost":"sample-dev","user":"old","write":"old"},
                               {"vhost":"another","user":"old","write":"unchanged"}],
                "queues":[{"vhost":"another","name":"old","arguments":{"keep":True}}]}

    def test_prepare_preserves_every_old_entry_and_is_exactly_repeatable(self):
        original = self.existing()
        baseline = copy.deepcopy(original)
        result = target.merge_definitions(original,**self.args())
        self.assertEqual(original,baseline)
        for kind in ("users","permissions","queues"):
            self.assertTrue(all(row in result[kind] for row in original[kind]))
        self.assertEqual(result["custom"],original["custom"])
        self.assertEqual(target.merge_definitions(result,**self.args()),result)

    def test_retirement_removes_only_explicit_permission_pair(self):
        result = target.merge_definitions(self.existing(),**self.args(),retire_users=("old",))
        self.assertFalse(any(p["vhost"]=="sample-dev" and p["user"]=="old" for p in result["permissions"]))
        self.assertTrue(any(p["vhost"]=="another" and p["user"]=="old" for p in result["permissions"]))
        self.assertIn(self.existing()["users"][0],result["users"])
        self.assertIn(self.existing()["queues"][0],result["queues"])

    def test_drift_duplicate_and_privileged_new_user_rejected(self):
        result = target.merge_definitions({},**self.args())
        drift = copy.deepcopy(result)
        drift["permissions"][0]["read"]=".*"
        duplicate = copy.deepcopy(result)
        duplicate["queues"].append(copy.deepcopy(duplicate["queues"][0]))
        for existing in (drift,duplicate):
            with self.assertRaises(ValueError):
                target.merge_definitions(existing,**self.args())
        args=self.args()
        args["users"][0]["tags"]=["administrator"]
        with self.assertRaises(ValueError):
            target.merge_definitions({},**args)

    def test_live_preparation_is_narrow_and_requires_existing_topology(self):
        args = self.args()
        live = target.broker_plan(args["vhost"], args["queue"], args["principals"])
        live["permissions"] = []
        original = copy.deepcopy(live)
        result = target.preparation_plan(self.existing(), live, **args)
        self.assertEqual(live, original)
        self.assertEqual(len(result["operations"]), 6)
        self.assertTrue(all(op["method"] == "PUT" for op in result["operations"]))
        self.assertEqual([op["path"].split("/")[0] for op in result["operations"]],
                         ["users"] * 3 + ["permissions"] * 3)
        for kind in ("queues", "exchanges", "bindings", "vhosts"):
            broken = copy.deepcopy(live)
            broken[kind] = []
            with self.assertRaisesRegex(ValueError, "topology"):
                target.preparation_plan({}, broken, **args)
        for field, row in (("users", args["users"][0]), ("permissions", {"user": args["users"][0]["name"]})):
            broken = copy.deepcopy(live)
            broken.setdefault(field, []).append(row)
            with self.assertRaisesRegex(ValueError, "already exists"):
                target.preparation_plan({}, broken, **args)
