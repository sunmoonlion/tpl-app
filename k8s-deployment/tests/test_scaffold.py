from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ScaffoldTest(unittest.TestCase):
    def command(self, output: Path) -> list[str]:
        digest = "sha256:" + "a" * 64
        return [
            "python3",
            str(ROOT / "scaffold.py"),
            "--app",
            "demo",
            "--namespace",
            "demo-v2",
            "--release-id",
            "r3-001",
            "--backend-image",
            f"registry.example/backend@{digest}",
            "--admin-image",
            f"registry.example/admin@{digest}",
            "--web-image",
            f"registry.example/web@{digest}",
            "--admin-origin",
            "https://demo-admin.example.test",
            "--web-origin",
            "https://demo.example.test",
            "--casdoor-origin",
            "https://identity.example.test",
            "--casdoor-namespace",
            "identity-system",
            "--tls-secret",
            "demo-tls",
            "--output-dir",
            str(output),
        ]

    def test_renders_locked_bundle_without_unresolved_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            subprocess.run(self.command(output), check=True, capture_output=True)
            release = json.loads((output / "release.json").read_text())
            self.assertEqual(release["app"], "demo")
            self.assertFalse(release["formal_release"])
            self.assertEqual(len(release["sha256"]), 5)
            self.assertEqual(
                release["dependencies"]["casdoor_namespace"], "identity-system"
            )
            all_yaml = "".join(
                (output / name).read_text() for name in release["resources"]
            )
            self.assertNotIn("__APP__", all_yaml)
            self.assertIn("demo-backend-api", all_yaml)
            self.assertIn("demo-admin-frontend", all_yaml)
            self.assertIn("demo-web-frontend", all_yaml)
            prerequisites = (output / "00-prerequisites.yaml").read_text()
            runtime = (output / "20-runtime.yaml").read_text()
            self.assertIn("- app.cli.worker_readiness", runtime)
            self.assertNotIn("inspect ping", runtime)
            self.assertIn("timeoutSeconds: 8", runtime)
            worker = runtime.split("name: demo-backend-worker\n", 1)[1].split("---", 1)[0]
            self.assertIn("sunmoonai.com/release-id: r3-001", worker)
            for role in ("API", "WORKER", "SCHEDULER"):
                self.assertIn(f"key: {role}_DATABASE_URL", runtime)
                self.assertIn(f"key: {role}_CELERY_BROKER_URL", runtime)
            # runner role is opt-in: with the default 0 replicas no runner resource is rendered
            self.assertNotIn("backend-runner", runtime)
            self.assertNotIn("backend-runner", prerequisites)
            self.assertIn('CELERY_WORKER_CONCURRENCY: "2"', prerequisites)
            self.assertIn(
                '--concurrency="${CELERY_WORKER_CONCURRENCY}"', runtime
            )
            policies = (output / "30-network-policies.yaml").read_text()
            self.assertIn("kubernetes.io/metadata.name: identity-system", policies)
            self.assertNotIn("backend-runner", policies)
            self.assertIn("app: casdoor-sunmoonai", policies)

    def test_runner_role_renders_when_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            subprocess.run(self.command(output) + ["--runner-replicas", "1"], check=True, capture_output=True)
            prerequisites = (output / "00-prerequisites.yaml").read_text()
            runtime = (output / "20-runtime.yaml").read_text()
            policies = (output / "30-network-policies.yaml").read_text()
            self.assertIn("name: demo-backend-runner\n", prerequisites)  # ServiceAccount
            runner = runtime.split("name: demo-backend-runner\n", 1)[1].split("---", 1)[0]
            self.assertIn("replicas: 1", runner)
            self.assertIn("type: Recreate", runner)
            self.assertIn("app.bootstrap.runner", runner)
            self.assertIn("key: API_DATABASE_URL", runner)  # shares the api identity
            self.assertNotIn("RUNNER_DATABASE_URL", runtime)
            self.assertNotIn("kind: HorizontalPodAutoscaler\nmetadata:\n  name: demo-backend-runner", runtime)
            self.assertIn("name: demo-backend-runner-egress", policies)
            self.assertIn('sunmoonai.com/sandbox-pool: "true"', policies)
            # the other documents are byte-identical to the default render
            default = Path(directory) / "default"
            subprocess.run(self.command(default), check=True, capture_output=True)
            for name in ("10-migration.yaml", "40-ingress.yaml"):
                self.assertEqual((output / name).read_bytes(), (default / name).read_bytes())

    def test_runner_replicas_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            command = self.command(Path(directory) / "bundle") + ["--runner-replicas", "21"]
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runner-replicas", result.stderr)

    def test_rejects_mutable_image_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            command = self.command(Path(directory) / "bundle")
            index = command.index("--backend-image") + 1
            command[index] = "registry.example/backend:latest"
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("repository@sha256", result.stderr)

    def test_rejects_insecure_public_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            command = self.command(Path(directory) / "bundle")
            index = command.index("--admin-origin") + 1
            command[index] = "http://demo-admin.example.test"
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("HTTPS", result.stderr)


if __name__ == "__main__":
    unittest.main()
