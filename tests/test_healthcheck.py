"""Optional real-Docker readiness regression test, run with JP_DOCKER_TEST=1."""
import os
import tempfile
import time
import uuid
import unittest
from pathlib import Path
from jp.common import image, run


@unittest.skipUnless(os.environ.get('JP_DOCKER_TEST') == '1', 'Docker regression is opt-in')
class ListenerHealthTests(unittest.TestCase):
    def test_live_listener_passes_and_missing_listener_fails(self):
        from jp.common import ROOT, write_private
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'runtime'
            root.mkdir(mode=0o755)
            write_private(root / 'server.yaml', {'mixed-port':17890,'log-level':'silent','rules':['MATCH,DIRECT']})
            write_private(root / 'healthcheck.sh', (ROOT / 'scripts/healthcheck.sh').read_text())
            write_private(root / 'listeners.expected', 'tcp 45E2\n')
            for p in root.iterdir():
                os.chmod(p, 0o644)
            name = 'jp-healthcheck-' + uuid.uuid4().hex[:8]
            run(['docker','run','-d','--name',name,'--network','none','--user','10001:10001',
                 '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
                 '--tmpfs','/tmp:rw,size=32m,mode=1777',
                 '--mount',f'type=bind,src={root},dst=/config,readonly',
                 image(),'-d','/tmp/mihomo','-f','/config/server.yaml'])
            try:
                for _ in range(20):
                    r = run(['docker','exec',name,'/bin/sh','/config/healthcheck.sh'],check=False)
                    if r.returncode == 0:
                        break
                    time.sleep(.2)
                self.assertEqual(r.returncode, 0, 'A real open listener must be healthy')
                write_private(root / 'listeners.expected', 'tcp FFFF\n')
                os.chmod(root / 'listeners.expected', 0o644)
                r = run(['docker','exec',name,'/bin/sh','/config/healthcheck.sh'],check=False)
                self.assertNotEqual(r.returncode, 0)
            finally:
                run(['docker','rm','-f',name],check=False)

    def test_missing_listener_cannot_be_healthy(self):
        # A parse-only check would accept the valid empty config but cannot satisfy a listener.
        from jp.common import ROOT, write_private
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'runtime'
            root.mkdir(mode=0o755)
            write_private(root / 'server.yaml', {'log-level':'silent','rules':['MATCH,DIRECT']})
            write_private(root / 'healthcheck.sh', (ROOT / 'scripts/healthcheck.sh').read_text())
            write_private(root / 'listeners.expected', 'tcp FFFF\n')
            for p in root.iterdir():
                os.chmod(p, 0o644)
            r = run(['docker','run','--rm','--network','none','--user','10001:10001',
                     '--mount',f'type=bind,src={root},dst=/config,readonly',
                     '--entrypoint','/bin/sh',image(),'/config/healthcheck.sh'],check=False)
            self.assertNotEqual(r.returncode, 0)
