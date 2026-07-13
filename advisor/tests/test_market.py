"""Tests for the M2 market/fee collectors' parsing layer.

Fixtures reproduce the real payload shapes captured from the live testnet
session (setup/pool.md, repo-reviews/loop.md), so the parsers are tested
against reality rather than invented JSON.
"""

from advisor.collectors.fee_collector import parse_recommended
from advisor.collectors.loop_collector import parse_in_quote, parse_out_quote
from advisor.collectors.pool_collector import (
    build_pool_market,
    parse_clearing_rates,
    parse_depth,
)

# ------------------------------------------------------------------ fees --

def test_fee_parse_maps_tiers_to_targets():
    env = parse_recommended(
        {"fastestFee": 25, "halfHourFee": 12, "hourFee": 6, "economyFee": 1,
         "minimumFee": 1},
        source="test",
    )
    assert env.available
    assert env.sat_per_vb == {1: 25.0, 3: 12.0, 6: 6.0, 144: 1.0}


def test_fee_at_target_picks_at_or_above():
    env = parse_recommended(
        {"fastestFee": 25, "halfHourFee": 12, "hourFee": 6, "economyFee": 1},
        source="test",
    )
    assert env.at_target(1) == 25.0
    assert env.at_target(2) == 12.0   # next available >= 2 is 3
    assert env.at_target(6) == 6.0
    assert env.at_target(500) == 1.0  # beyond max → cheapest known


def test_fee_parse_empty_payload():
    env = parse_recommended({}, source="test")
    assert not env.available


# ------------------------------------------------------------------ pool --

# Shape from the real `pool getinfo` market_info (setup/pool.md §1).
MARKET_INFO = {
    "2016": {
        "num_asks": [{"tier": "TIER_0", "value": 21}, {"tier": "TIER_1", "value": 9}],
        "num_bids": [{"tier": "TIER_0", "value": 13}, {"tier": "TIER_1", "value": 34}],
        "ask_open_interest_units": [
            {"tier": "TIER_0", "value": 164}, {"tier": "TIER_1", "value": 274}],
        "bid_open_interest_units": [
            {"tier": "TIER_0", "value": 87}, {"tier": "TIER_1", "value": 683}],
    },
}

# Shape from the real `pool auction snapshot` (setup/pool.md §1).
SNAPSHOT = [
    {
        "batch_id": "02ed14…",
        "batch_tx_id": "98be9d…",
        "matched_markets": {
            "2016": {
                "matched_orders": [{"matching_rate": 6613}],
                "clearing_price_rate": 6613,
            }
        },
    },
    {   # older batch with a different market — must not override newer
        "batch_id": "021774…",
        "matched_markets": {
            "2016": {"clearing_price_rate": 9999},
            "4032": {"clearing_price_rate": 1200},
        },
    },
]


def test_depth_sums_tiers():
    depth = parse_depth(MARKET_INFO)
    d = depth[2016]
    assert (d.asks, d.bids) == (30, 47)
    assert (d.ask_units, d.bid_units) == (438, 770)


def test_clearing_rates_newest_batch_wins():
    rates = parse_clearing_rates(SNAPSHOT)
    assert rates[2016] == 6613   # newest, not 9999
    assert rates[4032] == 1200   # picked up from the older batch


def test_build_pool_market_full():
    m = build_pool_market(
        fee={"execution_fee": {"base_fee": "1", "fee_rate": "1000"}},
        durations={"lease_duration_buckets": {"2016": "MARKET_OPEN"}},
        next_batch={"fee_rate_sat_per_kw": "6250", "clear_timestamp": "1783531468"},
        info={"market_info": MARKET_INFO},
        snapshot=SNAPSHOT,
    )
    assert m.connected
    assert m.exec_fee_base_sat == 1 and m.exec_fee_rate_ppm == 1000
    assert m.lease_durations == {2016: "MARKET_OPEN"}
    assert m.next_batch_feerate_sat_kw == 6250
    assert m.depth[2016].bids == 47
    assert m.last_clearing_rate_ppb[2016] == 6613


def test_build_pool_market_disconnected():
    assert not build_pool_market(None, None, None, None, None).connected


# ------------------------------------------------------------------ loop --

def test_loop_out_quote_totals_include_prepay():
    q = parse_out_quote(
        {"swap_fee_sat": "552", "htlc_sweep_fee_sat": "7280",
         "prepay_amt_sat": "1330"},
        amount_sat=500_000,
    )
    assert q.total_fee_sat == 552 + 7280 + 1330
    assert q.prepay_sat == 1330


def test_loop_in_quote_no_prepay():
    q = parse_in_quote(
        {"swap_fee_sat": "417", "htlc_publish_fee_sat": "550"},
        amount_sat=500_000,
    )
    assert q.total_fee_sat == 967
    assert q.prepay_sat == 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all market tests passed")
