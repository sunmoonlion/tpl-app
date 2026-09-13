import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "integration"))
from broker_test_support import select_auxiliary, select_backend


class BrokerTargetTest(unittest.TestCase):
    def test_only_initialized_sibling_backend_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            deployment = root / "tpl-app/k8s-deployment"
            deployment.mkdir(parents=True)
            backend = root / "sample-app/sample-backend/app"
            (backend / "app").mkdir(parents=True)
            (backend / "app/worker.py").touch()
            self.assertEqual(select_backend(deployment, str(backend)), backend)
            for invalid in (
                root,
                root.parent,
                backend.parent,
                backend / "app",
                root / "missing-app/missing-backend/app",
            ):
                with self.assertRaises(ValueError):
                    select_backend(deployment, str(invalid))

    def test_auxiliary_cannot_be_an_external_service_url(self):
        for value in ("none", "s3", "redis"):
            self.assertEqual(select_auxiliary(value), value)
        for value in ("http://127.0.0.1:9000", "production", "", "all"):
            with self.assertRaises(ValueError):
                select_auxiliary(value)
