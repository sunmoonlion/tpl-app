from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "deployment_config", ROOT / "deployment_config.py"
)
assert SPEC and SPEC.loader
CONFIG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFIG)


class DeploymentConfigTest(unittest.TestCase):
    def base_text(self) -> str:
        digest = "sha256:" + "a" * 64
        return "\n".join(
            (
                "CONFIG_VERSION=1",
                "APP=demo",
                "DEFAULT_PROFILE=KIND",
                "BUNDLE_DIR=deployment/bundle",
                "DEPLOY_SCRIPT=deployment/deploy.py",
                "NAMESPACE=demo-system",
                "RELEASE_ID=demo-001",
                f"BACKEND_IMAGE=registry.example/backend@{digest}",
                f"ADMIN_IMAGE=registry.example/admin@{digest}",
                f"WEB_IMAGE=registry.example/web@{digest}",
                "ADMIN_ORIGIN=https://demo-admin.example.test",
                "WEB_ORIGIN=https://demo.example.test",
                "CASDOOR_ORIGIN=https://identity.example.test",
                "API_REPLICAS=2",
                "WORKER_REPLICAS=1",
                "SCHEDULER_REPLICAS=1",
                "ADMIN_REPLICAS=2",
                "WEB_REPLICAS=2",
                "",
            )
        )

    def test_loads_strict_config_and_matches_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deploy.conf"
            path.write_text(self.base_text(), encoding="utf-8")
            config = CONFIG.load_base(path)
            release = {
                "logical_app": "demo",
                "resource_app": "demo-r5",
                "namespace": "demo-system",
                "release_id": "demo-001",
                "images": {
                    "backend": config["BACKEND_IMAGE"],
                    "admin": config["ADMIN_IMAGE"],
                    "web": config["WEB_IMAGE"],
                },
                "origins": {
                    "admin": config["ADMIN_ORIGIN"],
                    "web": config["WEB_ORIGIN"],
                    "casdoor": config["CASDOOR_ORIGIN"],
                },
                "deployment_replicas": {
                    "demo-r5-backend-api": 2,
                    "demo-r5-backend-worker": 1,
                    "demo-r5-backend-scheduler": 1,
                    "demo-r5-admin-frontend": 2,
                    "demo-r5-web-frontend": 2,
                },
            }
            CONFIG.validate_release(config, release)

    def test_repository_example_uses_the_strict_schema(self):
        config = CONFIG.load_base(
            ROOT / "config-example" / "deploy-demo-app-all.conf"
        )
        profile = CONFIG.load_profile(
            ROOT / "config-example" / "profiles" / "KIND.conf"
        )
        self.assertEqual(config["APP"], "demo")
        self.assertEqual(profile["PROFILE_ENABLED"], "true")

    def test_rejects_unknown_or_shell_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deploy.conf"
            path.write_text(
                self.base_text() + "UNKNOWN=$(id)\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(CONFIG.ConfigError, "unknown configuration key"):
                CONFIG.load_base(path)

    def test_rejects_runtime_override_of_immutable_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deploy.conf"
            path.write_text(self.base_text(), encoding="utf-8")
            config = CONFIG.load_base(path)
            release = {
                "logical_app": "demo",
                "resource_app": "demo-r5",
                "namespace": "another-system",
                "release_id": "demo-001",
                "images": {key: config[f"{key.upper()}_IMAGE"] for key in ("backend", "admin", "web")},
                "origins": {key: config[f"{key.upper()}_ORIGIN"] for key in ("admin", "web", "casdoor")},
                "deployment_replicas": {
                    "demo-r5-backend-api": 2,
                    "demo-r5-backend-worker": 1,
                    "demo-r5-backend-scheduler": 1,
                    "demo-r5-admin-frontend": 2,
                    "demo-r5-web-frontend": 2,
                },
            }
            with self.assertRaisesRegex(CONFIG.ConfigError, "render and gate a new release"):
                CONFIG.validate_release(config, release)


if __name__ == "__main__":
    unittest.main()
