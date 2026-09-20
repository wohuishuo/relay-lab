import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from contextlib import ExitStack
from jp.quickstart import plan, apply, install_steps
from jp.config import client_config, example_secrets


class QuickstartTests(unittest.TestCase):
    def settings(self):
        return {'server': 'node.test.net', 'domain': 'node.test.net', 'reality_sni': 'target.test.net',
                'reality_dest': 'target.test.net:443', 'protocols': ['reality', 'hy2']}

    def test_plan_has_no_side_effects_and_only_selected_ports(self):
        with tempfile.TemporaryDirectory() as temp, patch('jp.quickstart.run') as run:
            state = Path(temp) / 'absent'
            result = plan(self.settings(), state)
            self.assertFalse(state.exists())
            run.assert_not_called()
            self.assertEqual(result['inbound'], [{'protocol': 'tcp', 'port': 443}, {'protocol': 'udp', 'port': 443}])

    def pipeline(self, stack, *, acme_failure=False, deploy_failure=False):
        calls = []
        def operation(name, result=None, fail=False):
            def perform(*args, **kwargs):
                calls.append(name)
                if fail:
                    raise RuntimeError('simulated failure')
                return result
            return perform
        stack.enter_context(patch('jp.quickstart.run', side_effect=operation('command')))
        stack.enter_context(patch('jp.tools.install_tools', side_effect=operation('tools')))
        stack.enter_context(patch('jp.certificates.acme', side_effect=operation('acme', ('cert', 'key'), acme_failure)))
        stack.enter_context(patch('jp.certificates.install_pair', side_effect=operation('cert-install')))
        stack.enter_context(patch('jp.operations.prepare', side_effect=operation('prepare', 'release-id')))
        stack.enter_context(patch('jp.operations.deploy', side_effect=operation('deploy', fail=deploy_failure)))
        stack.enter_context(patch('jp.quickstart.read_json', return_value=client_config('hy2', example_secrets(), 'node.example.com', 'node.example.com', 'www.example.org')))
        stack.enter_context(patch('jp.quickstart.write_private', side_effect=operation('write')))
        return calls

    def test_acme_failure_prevents_prepare_or_deploy(self):
        with ExitStack() as stack:
            calls = self.pipeline(stack, acme_failure=True)
            with self.assertRaises(RuntimeError):
                install_steps(self.settings(), Path('/var/lib/relay-lab'), 'owner@example.com', Path('/private/token.json'))
            self.assertNotIn('prepare', calls)
            self.assertNotIn('deploy', calls)
            self.assertNotIn('write', calls)

    def test_deployment_failure_prevents_export_and_timer(self):
        with ExitStack() as stack:
            calls = self.pipeline(stack, deploy_failure=True)
            with self.assertRaises(RuntimeError):
                install_steps(self.settings(), Path('/var/lib/relay-lab'), 'owner@example.com', Path('/private/token.json'))
            self.assertEqual(calls[-1], 'deploy')
            self.assertNotIn('write', calls)

    def test_successful_orchestration_order_with_mocked_side_effects(self):
        with ExitStack() as stack:
            calls = self.pipeline(stack)
            self.assertEqual(install_steps(self.settings(), Path('/var/lib/relay-lab'), 'owner@example.com', Path('/private/token.json')), 'release-id')
            self.assertEqual(calls[:9], ['command', 'command', 'command', 'tools', 'acme', 'acme', 'cert-install', 'prepare', 'deploy'])
            self.assertEqual(calls[-2:], ['command', 'command'])

    def test_existing_release_and_missing_acknowledgments_refused(self):
        with tempfile.TemporaryDirectory() as temp, patch('jp.quickstart.run') as run:
            with self.assertRaises(ValueError):
                apply(self.settings(), temp, 'owner@example.com', '/missing')
            (Path(temp) / 'active.json').write_text('{}')
            with self.assertRaises(ValueError):
                plan(self.settings(), temp)
            run.assert_not_called()
