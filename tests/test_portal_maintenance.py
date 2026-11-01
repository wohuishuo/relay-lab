import json
from unittest import TestCase, mock
from portal import node_action


class NodeMaintenanceTests(TestCase):
    def setUp(self):
        self.pin = "sha256:" + "1" * 64
        self.tag = "SHA256:" + "A" * 43
        self.obj = {
            "Id": "test-container",
            "RestartCount": 0,
            "Config": {
                "Image": "metacubex/mihomo@" + self.pin,
                "Labels": {"com.docker.compose.project": "jp-proxy", "com.docker.compose.service": "mihomo"},
            },
            "State": {"Health": {"Status": "healthy"}, "StartedAt": "2026-11-01T00:00:00.000Z"},
        }
        self.calls = []

        def command(args, **kwargs):
            self.calls.append(args)
            output = {
                "ssh-keygen": "256 " + self.tag + " host",
                "docker": json.dumps([self.obj]),
                "systemctl": "not-found",
            }
            return mock.Mock(stdout=output.get(args[0], ""))

        self.enterContext(mock.patch.object(node_action.os, "geteuid", return_value=0, create=True))
        self.enterContext(mock.patch.object(node_action.subprocess, "run", side_effect=command))

    def test_update_current_is_readonly(self):
        self.assertEqual(node_action.perform("update", self.tag, self.pin), {"result": "current"})
        self.assertEqual([r[0] for r in self.calls], ["ssh-keygen", "docker"])

    def test_update_missing_stage_refused(self):
        self.assertEqual(node_action.perform("update", self.tag, "other"), {"result": "needs_staging"})
        self.assertFalse(any("start" in r for r in self.calls))

    def test_restart_only_verified_container(self):
        self.assertEqual(node_action.perform("restart", self.tag, self.pin), {"result": "restart_scheduled"})
        self.assertEqual(
            self.calls[-1][-5:], ["/usr/bin/docker", "restart", "--time", "10", "test-container"]
        )
        self.obj["State"]["Health"]["Status"] = "unhealthy"
        self.assertEqual(node_action.perform("restart", self.tag, self.pin), {"result": "preflight_failed"})

    def test_wrong_host_refused_before_docker(self):
        self.assertEqual(
            node_action.perform("restart", "untrusted", self.pin), {"result": "identity_mismatch"}
        )
        self.assertEqual([r[0] for r in self.calls], ["ssh-keygen"])
