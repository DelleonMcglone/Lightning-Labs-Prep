"""Per-channel and node-level liquidity signals (SPEC M1, FR5).

Follows Faraday's method (repo-reviews/faraday.md §2):
- filter out private and too-young channels before any statistics;
- normalize metrics by committed capital and time before comparing
  (here: per capacity-day — sats of activity per sat-day committed);
- flag *lower* IQR outliers relative to this node's own channels — a channel
  is "underperforming" only versus its siblings, never versus a magic number.

Everything is a pure function of the snapshot; no I/O.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from ..models import ChannelState, NodeSnapshot
from .dataset import DEFAULT_OUTLIER_MULTIPLIER, Dataset

# A channel younger than this isn't judged (Faraday's MinimumMonitored idea).
MIN_MONITORED_SECONDS = 24 * 3600

# Balance below this fraction on either side = the channel is one-sided.
IMBALANCE_THRESHOLD = 0.2


class ChannelSignals(BaseModel):
    """Deterministic signals for one channel."""

    chan_point: str
    chan_id: int
    peer_pubkey: str
    capacity_sat: int

    # Balance / availability
    local_ratio: float          # 0 = all inbound, 1 = all outbound
    imbalance: float            # 0 = perfectly balanced, 1 = fully one-sided
    one_sided: bool             # local_ratio outside [0.2, 0.8]
    uptime_ratio: float
    active: bool
    private: bool
    monitored_s: int
    considered: bool            # eligible for outlier comparison?
    excluded_reason: Optional[str] = None

    # Routing performance over the forwarding lookback window,
    # normalized per capacity-day (activity per sat-day of committed capital).
    forwards_in: int = 0
    forwards_out: int = 0
    fees_earned_msat: int = 0
    volume_sat: int = 0
    revenue_per_capacity_day: float = 0.0
    volume_per_capacity_day: float = 0.0

    # Faraday-style lower-outlier flags vs. this node's other channels.
    revenue_outlier_low: bool = False
    volume_outlier_low: bool = False
    uptime_outlier_low: bool = False


class NodeSignals(BaseModel):
    """Node-level aggregates the recommendation engine consumes."""

    total_inbound_sat: int
    total_outbound_sat: int
    inbound_ratio: float        # share of total active capacity that is inbound
    channels_total: int
    channels_considered: int
    channels_one_sided: int
    outlier_multiplier: float
    forwarding_lookback_days: int
    channels: list[ChannelSignals]


def _capacity_days(c: ChannelState) -> float:
    """Sat-days of committed capital, from capacity × monitored lifetime."""
    return c.capacity_sat * (c.lifetime_s / 86_400)


def compute_signals(
    snap: NodeSnapshot,
    outlier_multiplier: float = DEFAULT_OUTLIER_MULTIPLIER,
    min_monitored_s: int = MIN_MONITORED_SECONDS,
) -> NodeSignals:
    """Compute all M1 signals from a snapshot. Pure and deterministic."""
    per_channel: list[ChannelSignals] = []

    for c in snap.channels:
        fwd = snap.forwarding.get(c.chan_id)
        fees_msat = fwd.fee_msat if fwd else 0
        vol = (fwd.amt_in_sat + fwd.amt_out_sat) if fwd else 0
        cap_days = _capacity_days(c)

        considered = True
        reason = None
        if c.private:
            considered, reason = False, "private"
        elif c.lifetime_s < min_monitored_s:
            considered, reason = False, "monitored < 24h"

        local_ratio = c.local_ratio
        per_channel.append(
            ChannelSignals(
                chan_point=c.chan_point,
                chan_id=c.chan_id,
                peer_pubkey=c.peer_pubkey,
                capacity_sat=c.capacity_sat,
                local_ratio=local_ratio,
                imbalance=abs(local_ratio - 0.5) * 2,
                one_sided=(
                    local_ratio < IMBALANCE_THRESHOLD
                    or local_ratio > 1 - IMBALANCE_THRESHOLD
                ),
                uptime_ratio=c.uptime_ratio,
                active=c.active,
                private=c.private,
                monitored_s=c.lifetime_s,
                considered=considered,
                excluded_reason=reason,
                forwards_in=fwd.events_in if fwd else 0,
                forwards_out=fwd.events_out if fwd else 0,
                fees_earned_msat=fees_msat,
                volume_sat=vol,
                revenue_per_capacity_day=(
                    (fees_msat / 1000) / cap_days if cap_days else 0.0
                ),
                volume_per_capacity_day=vol / cap_days if cap_days else 0.0,
            )
        )

    # Outlier detection over the considered channels only.
    eligible = [s for s in per_channel if s.considered]
    _flag_low_outliers(
        eligible, "revenue_per_capacity_day", "revenue_outlier_low",
        outlier_multiplier,
    )
    _flag_low_outliers(
        eligible, "volume_per_capacity_day", "volume_outlier_low",
        outlier_multiplier,
    )
    _flag_low_outliers(
        eligible, "uptime_ratio", "uptime_outlier_low", outlier_multiplier
    )

    total_in = snap.total_inbound_sat
    total_out = snap.total_outbound_sat
    total = total_in + total_out
    return NodeSignals(
        total_inbound_sat=total_in,
        total_outbound_sat=total_out,
        inbound_ratio=total_in / total if total else 0.0,
        channels_total=len(per_channel),
        channels_considered=len(eligible),
        channels_one_sided=sum(1 for s in per_channel if s.one_sided),
        outlier_multiplier=outlier_multiplier,
        forwarding_lookback_days=snap.forwarding_lookback_days,
        channels=per_channel,
    )


def _flag_low_outliers(
    signals: list[ChannelSignals],
    value_attr: str,
    flag_attr: str,
    multiplier: float,
) -> None:
    """Mark lower-IQR-outlier channels for one metric (in place)."""
    data = Dataset(
        {s.chan_point: getattr(s, value_attr) for s in signals}
    )
    outliers = data.get_outliers(multiplier)
    for s in signals:
        result = outliers.get(s.chan_point)
        if result is not None:
            setattr(s, flag_attr, result.lower_outlier)
