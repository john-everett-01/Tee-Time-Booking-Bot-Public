# System clock drift is the enemy of firing at an exact release moment, so scheduling
# decisions run off an NTP-corrected offset rather than trusting the local clock outright.

from __future__ import annotations

import time as time_module
from datetime import datetime, timedelta

import ntplib

NTP_SERVERS = ["pool.ntp.org", "time.google.com", "time.cloudflare.com"]


def ntp_offset_seconds(servers=NTP_SERVERS, timeout: float = 5.0) -> float:
    client = ntplib.NTPClient()
    errors = []
    for server in servers:
        try:
            response = client.request(server, version=3, timeout=timeout)
            return response.offset
        except Exception as exc:
            errors.append(f"{server}: {exc}")
    raise RuntimeError(f"all NTP servers failed: {'; '.join(errors)}")


def make_now(offset_seconds: float):
    def now() -> datetime:
        return datetime.now() + timedelta(seconds=offset_seconds)

    return now


def sleep_until(target: datetime, now_fn) -> None:
    while True:
        remaining = (target - now_fn()).total_seconds()
        if remaining <= 0:
            return
        if remaining > 5:
            time_module.sleep(min(remaining - 5, 30))
        else:
            time_module.sleep(0.05)
