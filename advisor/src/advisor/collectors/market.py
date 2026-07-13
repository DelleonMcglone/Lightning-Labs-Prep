"""Assemble the full MarketSnapshot from the three M2 collectors."""

from __future__ import annotations

from ..config import Settings
from ..models import MarketSnapshot
from .fee_collector import collect_fees
from .loop_collector import collect_loop_market
from .pool_collector import collect_pool_market


def collect_market(settings: Settings) -> MarketSnapshot:
    """Collect fees + Pool + Loop state. Each part degrades independently."""
    return MarketSnapshot(
        fees=collect_fees(settings.mempool_api_base),
        pool=collect_pool_market(settings.pool_bin, settings.network),
        loop=collect_loop_market(
            settings.loop_rest_host,
            settings.loop_dir,
            settings.network,
            settings.quote_amount_sat,
        ),
    )
