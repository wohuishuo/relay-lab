import json
from pathlib import Path
import sys
import time
import urllib.request

deadline = time.monotonic() + 35
while time.monotonic() < deadline:
    try:
        request = urllib.request.Request('http://client:19091/proxies/Auto',
                    headers={'Authorization': 'Bearer ' + Path('/private/api-secret.txt').read_text().strip()})
        with urllib.request.urlopen(request, timeout=3) as response:
            selected = json.load(response)['now']
        if selected == sys.argv[1]:
            print(json.dumps({'selected': selected, 'passed': True}))
            sys.exit(0)
    except Exception:
        pass
    time.sleep(.5)
print(json.dumps({'passed': False}))
sys.exit(1)
