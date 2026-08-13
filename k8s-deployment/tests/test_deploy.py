from __future__ import annotations

import argparse
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("k8s_deploy", ROOT / "deploy.py")
assert SPEC and SPEC.loader
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class ComponentDeployTest(unittest.TestCase):
    def test_runtime_component_selects_only_one_deployment_family(self):
        documents = [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "demo-backend-api"},
            },
            {
                "apiVersion": "policy/v1",
                "kind": "PodDisruptionBudget",
                "metadata": {"name": "demo-backend-api"},
            },
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "demo-backend-worker"},
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "20-runtime.yaml").write_text(
                yaml.safe_dump_all(documents, sort_keys=False), encoding="utf-8"
            )
            captured: dict[str, bytes] = {}

            def fake_kubectl(_args, *items, **kwargs):
                captured["items"] = " ".join(items).encode()
                captured["payload"] = kwargs["input_bytes"]
                return subprocess.CompletedProcess(items, 0)

            with patch.object(DEPLOY, "kubectl", side_effect=fake_kubectl):
                DEPLOY.apply_runtime_component(
                    argparse.Namespace(), bundle, "demo-backend-api"
                )

        selected = [
            item
            for item in yaml.safe_load_all(captured["payload"].decode())
            if item
        ]
        self.assertEqual(captured["items"], b"apply -f -")
        self.assertEqual(len(selected), 2)
        self.assertEqual(
            {item["metadata"]["name"] for item in selected}, {"demo-backend-api"}
        )
        self.assertIn("Deployment", {item["kind"] for item in selected})


if __name__ == "__main__":
    unittest.main()
