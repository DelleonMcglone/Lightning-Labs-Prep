"""On-chain fee environment collector (SPEC FR4).

Reads mempool.space's recommended-fees endpoint and maps its named tiers to
confirmation targets. Degrades gracefully: any failure returns an
``available=False`` FeeEnvironment rather than raising — fee-aware rules
simply skip when the environment is unknown.
"""

from __future__ import annotations

import requests

from ..models import FeeEnvironment

# mempool.space tier name → approximate confirmation target (blocks).
_TIER_TO_TARGET = {
    "fastestFee": 1,
    "halfHourFee": 3,
    "hourFee": 6,
    "economyFee": 144,
}


def parse_recommended(payload: dict, source: str) -> FeeEnvironment:
    """Map a /v1/fees/recommended payload to a FeeEnvironment."""
    sat_per_vb = {
        target: float(payload[tier])
        for tier, target in _TIER_TO_TARGET.items()
        if tier in payload
    }
    return FeeEnvironment(
        available=bool(sat_per_vb), sat_per_vb=sat_per_vb, source=source
    )


def collect_fees(api_base: str, timeout: float = 10.0) -> FeeEnvironment:
    """Fetch current fee estimates; never raises."""
    url = f"{api_base}/v1/fees/recommended"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return parse_recommended(resp.json(), source=url)
    except Exception:
        return FeeEnvironment(available=False, source=url)
