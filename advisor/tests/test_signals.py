"""Tests for the M1 signal engine.

The IQR tests reproduce the exact worked example documented in Faraday's
dataset package (see repo-reviews/faraday.md §2d), so the Python port is
verified against the Go original's specified behavior.
"""

from advisor.models import (
    Balances,
    ChannelState,
    ForwardingStats,
    NodeIdentity,
    NodeSnapshot,
)
from advisor.signals import Dataset, compute_signals

# ---------------------------------------------------------------- dataset --

# Faraday's documented example: LQ=5, UQ=6, IQR=1.
FARADAY_EXAMPLE = {
    "a": 1.0, "b": 2.0, "c": 5.0, "d": 5.0, "e": 5.0,
    "f": 6.0, "g": 6.0, "h": 6.0, "i": 8.0, "j": 11.0,
}


def test_quartiles_match_faraday_example():
    lq, uq = Dataset(FARADAY_EXAMPLE).quartiles()
    assert (lq, uq) == (5.0, 6.0)


def test_strong_outliers_multiplier_3():
    out = Dataset(FARADAY_EXAMPLE).get_outliers(3.0)
    lows = {k for k, r in out.items() if r.lower_outlier}
    highs = {k for k, r in out.items() if r.upper_outlier}
    assert lows == {"a"}          # 1 < 5 - 3
    assert highs == {"j"}         # 11 > 6 + 3


def test_weak_outliers_multiplier_1_5():
    out = Dataset(FARADAY_EXAMPLE).get_outliers(1.5)
    lows = {k for k, r in out.items() if r.lower_outlier}
    highs = {k for k, r in out.items() if r.upper_outlier}
    assert lows == {"a", "b"}     # 1, 2 < 5 - 1.5
    assert highs == {"i", "j"}    # 8, 11 > 6 + 1.5


def test_too_few_values_returns_no_outliers():
    out = Dataset({"a": 1.0, "b": 100.0}).get_outliers(3.0)
    assert all(not r.lower_outlier and not r.upper_outlier for r in out.values())


def test_odd_count_excludes_median():
    # 5 values, exclusive method: lower half [1,2], upper half [8,9].
    lq, uq = Dataset({"a": 1, "b": 2, "c": 5, "d": 8, "e": 9}).quartiles()
    assert (lq, uq) == (1.5, 8.5)


def test_threshold():
    flags = Dataset({"a": 1.0, "b": 5.0}).get_threshold(2.0, below=True)
    assert flags == {"a": True, "b": False}


# ----------------------------------------------------------------- engine --

DAY = 86_400


def _channel(cp, chan_id, local, remote, lifetime_s=30 * DAY, **kw):
    return ChannelState(
        chan_point=cp,
        chan_id=chan_id,
        peer_pubkey=kw.get("peer", "03" + cp),
        capacity_sat=local + remote,
        local_sat=local,
        remote_sat=remote,
        active=kw.get("active", True),
        private=kw.get("private", False),
        uptime_s=kw.get("uptime_s", lifetime_s),
        lifetime_s=lifetime_s,
        total_sent_sat=0,
        total_received_sat=0,
    )


def _snapshot(channels, forwarding=None):
    return NodeSnapshot(
        identity=NodeIdentity(
            alias="t", pubkey="02", version="v", block_height=1,
            synced_to_chain=True, num_active_channels=len(channels),
            num_peers=len(channels),
        ),
        balances=Balances(
            onchain_confirmed=0, onchain_unconfirmed=0, ln_local=0, ln_remote=0
        ),
        channels=channels,
        forwarding=forwarding or {},
    )


def test_one_sided_and_imbalance():
    sig = compute_signals(_snapshot([
        _channel("bal:0", 1, 50_000, 50_000),
        _channel("out:0", 2, 95_000, 5_000),
        _channel("in:0", 3, 5_000, 95_000),
    ]))
    by = {s.chan_point: s for s in sig.channels}
    assert not by["bal:0"].one_sided and by["bal:0"].imbalance == 0
    assert by["out:0"].one_sided and abs(by["out:0"].imbalance - 0.9) < 1e-9
    assert by["in:0"].one_sided
    assert sig.channels_one_sided == 2


def test_filtering_private_and_young():
    sig = compute_signals(_snapshot([
        _channel("ok:0", 1, 1000, 1000),
        _channel("priv:0", 2, 1000, 1000, private=True),
        _channel("young:0", 3, 1000, 1000, lifetime_s=3600),
    ]))
    by = {s.chan_point: s for s in sig.channels}
    assert by["ok:0"].considered
    assert not by["priv:0"].considered and by["priv:0"].excluded_reason == "private"
    assert not by["young:0"].considered
    assert sig.channels_considered == 1


def test_revenue_outlier_flags_underperformer():
    # 7 equal-size, equal-age channels: six earn ~100 sats of fees, one earns
    # nothing. With a tight cluster the zero-earner is a clear lower outlier.
    # (With very few channels a zero drags the lower quartile down and is NOT
    # flagged — that's correct IQR behavior, matching Faraday.)
    fees = {1: 95_000, 2: 98_000, 3: 100_000, 4: 102_000, 5: 105_000, 6: 110_000}
    channels = [
        _channel(f"c{i}:0", i, 500_000, 500_000) for i in range(1, 8)
    ]
    forwarding = {
        cid: ForwardingStats(
            chan_id=cid, events_out=10, amt_out_sat=100_000, fee_msat=fee
        )
        for cid, fee in fees.items()
        # chan 7: no forwards at all
    }
    sig = compute_signals(_snapshot(channels, forwarding), outlier_multiplier=1.5)
    by = {s.chan_point: s for s in sig.channels}
    assert by["c7:0"].revenue_outlier_low
    assert not any(by[f"c{i}:0"].revenue_outlier_low for i in range(1, 7))
    # fee attribution: earned on outgoing side
    assert by["c1:0"].fees_earned_msat == 95_000


def test_zero_revenue_not_outlier_in_tiny_portfolio():
    # Documents the IQR property above: with only 4 channels, one zero-earner
    # is inside the natural spread and must NOT be flagged.
    channels = [_channel(f"c{i}:0", i, 500_000, 500_000) for i in range(1, 5)]
    forwarding = {
        i: ForwardingStats(chan_id=i, events_out=10, amt_out_sat=100_000,
                           fee_msat=100_000 + i * 5_000)
        for i in range(1, 4)
    }
    sig = compute_signals(_snapshot(channels, forwarding), outlier_multiplier=1.5)
    by = {s.chan_point: s for s in sig.channels}
    assert not by["c4:0"].revenue_outlier_low


def test_inbound_ratio():
    sig = compute_signals(_snapshot([
        _channel("a:0", 1, 75_000, 25_000),
    ]))
    assert sig.inbound_ratio == 0.25


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all signal tests passed")
