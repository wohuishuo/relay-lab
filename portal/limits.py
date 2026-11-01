"""Single-worker front-door budgets. Client addresses are keyed in memory and never logged."""
import hmac
import time

from django.conf import settings
from django.core.cache import cache

# Per-address and whole-service attempts per window, in seconds.
BUDGETS = {
    "/register/": (3600, 6, 40),
    "/login/": (600, 25, 200),
    "/questions/": (3600, 8, 100),
    "/apply/": (600, 15, 150),
    "/connect": (60, 80, 1200),
}


def allow(path, peer):
    window, per_client, total = BUDGETS[path]
    slot = int(time.time()) // window
    prefix = f"front:{path}:{slot}:"
    identifier = hmac.digest(settings.SECRET_KEY.encode(), peer, "sha256").hex()[:24]
    for key, maximum in [(prefix + identifier, per_client), (prefix + "all", total)]:
        cache.add(key, 0, timeout=window + 2)
        if cache.incr(key) > maximum:
            return False
    return True
