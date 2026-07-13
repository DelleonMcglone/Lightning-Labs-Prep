"""Tests for the M4 LLM layer: privacy filter, number contract, and the
enhance flow with a mocked Anthropic client (no network).

SPEC M4 exit criterion: "no sensitive data in the prompt (tested)" — that's
test_prompt_payload_contains_no_identifiers.
"""

import json

from advisor.config import Settings
from advisor.llm.advisor import EnhancedReport, enhance_report
from advisor.llm.privacy import (
    collect_numeric_facts,
    narrative_violations,
    sanitize_report,
)
from advisor.models import (
    Balances, ChannelState, FeeEnvironment, LoopMarket, LoopQuote,
    MarketSnapshot, NodeIdentity, NodeSnapshot, PoolMarket,
)
from advisor.recommend import recommend
from advisor.signals import compute_signals

DAY = 86_400
PEER = "03e84a109cd70e57864274932fc87c5e6434c59ebb8e6e7d28532219ba38f7f6df"
CHAN_POINT = ("f6d1afef96220d7225ac44d74e988a2c8ccfe26990782a0187f5fadc0eba6722"
              ":0")
NODE_PUB = "0308c82c33cd3e4964b141ed166da0e3820cc726e2d6f798bd986441f43cf92035"


def _snapshot():
    return NodeSnapshot(
        identity=NodeIdentity(
            alias="lightning-prep-testnet", pubkey=NODE_PUB, version="v",
            block_height=1, synced_to_chain=True, num_active_channels=1,
            num_peers=1,
        ),
        balances=Balances(onchain_confirmed=111_674, onchain_unconfirmed=0,
                          ln_local=20_515, ln_remote=1_014),
        channels=[ChannelState(
            chan_point=CHAN_POINT, chan_id=1, peer_pubkey=PEER,
            capacity_sat=25_000, local_sat=20_515, remote_sat=1_014,
            active=True, private=False, uptime_s=30 * DAY,
            lifetime_s=30 * DAY, total_sent_sat=0, total_received_sat=0,
        )],
    )


def _market():
    return MarketSnapshot(
        fees=FeeEnvironment(available=True,
                            sat_per_vb={1: 1.0, 3: 1.0, 6: 1.0, 144: 1.0}),
        pool=PoolMarket(
            connected=True, exec_fee_base_sat=1, exec_fee_rate_ppm=1_000,
            next_batch_feerate_sat_kw=6_250,
            last_clearing_rate_ppb={2016: 6_613},
            account_available_sat=200_000,
        ),
        loop=LoopMarket(
            connected=True, out_min_sat=250_000, out_max_sat=120_000_000,
            in_min_sat=250_000, in_max_sat=120_000_000,
            out_quote=LoopQuote(amount_sat=500_000, swap_fee_sat=552,
                                miner_fee_sat=7_280, prepay_sat=1_330),
            in_quote=LoopQuote(amount_sat=500_000, swap_fee_sat=417,
                               miner_fee_sat=550),
        ),
    )


def _pipeline():
    snap = _snapshot()
    sig = compute_signals(snap)
    report = recommend(snap, sig, _market())
    return snap, sig, report


# ---------------------------------------------------------------- privacy --

def test_prompt_payload_contains_no_identifiers():
    snap, sig, report = _pipeline()
    payload, _ = sanitize_report(report, sig, snap)
    blob = json.dumps(payload)
    assert PEER not in blob
    assert PEER[:16] not in blob
    assert CHAN_POINT not in blob
    assert CHAN_POINT.split(":")[0] not in blob
    assert NODE_PUB not in blob
    assert "lightning-prep-testnet" not in blob
    # aliases took their place
    assert "peer-A" in blob or "channel-1" in blob


def test_sanitize_keeps_numbers_intact():
    snap, sig, report = _pipeline()
    payload, _ = sanitize_report(report, sig, snap)
    blob = json.dumps(payload)
    assert "1014" in blob or "1,014" in blob      # inbound stays
    r1 = next(r for r in payload["recommendations"] if r["rule"] == "R1")
    assert r1["data"]["pool_total_sat"] == 1_333 + 101 + 8_750


# --------------------------------------------------------- number contract --

def test_narrative_violation_detection():
    snap, sig, report = _pipeline()
    facts = collect_numeric_facts(report, sig, snap)
    ok = "Your inbound is 1,014 sat, so a 100,000 sat lease costing " \
         "10,184 sat fixes the receive problem."
    assert narrative_violations(ok, facts) == []
    bad = "This will cost you about 12,500 sat all-in."
    assert narrative_violations(bad, facts) == ["12,500"]


def test_small_numbers_allowed_freely():
    snap, sig, report = _pipeline()
    facts = collect_numeric_facts(report, sig, snap)
    assert narrative_violations(
        "Your inbound share is about 5% across 1 channel over 30 days.",
        facts,
    ) == []


# ----------------------------------------------------------- enhance flow --

class _FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def __init__(self, reply):
        self._reply = reply
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self._reply)


class _FakeClient:
    def __init__(self, reply):
        self.messages = _FakeMessages(reply)


def test_enhance_uses_llm_text_when_numbers_check_out():
    snap, sig, report = _pipeline()
    reply = json.dumps([{
        "id": "R1-0", "rank": 1,
        "headline": "You can barely receive — fix inbound now",
        "narrative": "Almost all channel balance sits on your side, so "
                     "payments toward you bounce. A 100,000 sat lease "
                     "costing 10,184 sat restores receive headroom.",
        "priority_reason": "receive failures are silent",
    }])
    fake = _FakeClient(reply)
    enh = enhance_report(report, sig, snap, Settings(), client=fake)
    assert isinstance(enh, EnhancedReport)
    item = enh.items[0]
    assert item.narrative_from_llm
    assert "barely receive" in item.headline
    # deterministic command survives untouched
    assert "pool orders submit bid" in item.rec.command
    # and the prompt that went out was sanitized
    sent = json.dumps(fake.messages.last_kwargs["messages"])
    assert PEER not in sent and NODE_PUB not in sent


def test_enhance_falls_back_on_bad_numbers():
    snap, sig, report = _pipeline()
    reply = json.dumps([{
        "id": "R1-0", "rank": 1,
        "headline": "Fix inbound",
        "narrative": "This lease will cost roughly 99,999 sat in total.",
    }])
    enh = enhance_report(report, sig, snap, Settings(),
                         client=_FakeClient(reply))
    item = enh.items[0]
    assert not item.narrative_from_llm          # rejected
    assert item.narrative == report.recommendations[0].summary


def test_enhance_keeps_dropped_recs_in_engine_order():
    snap, sig, report = _pipeline()
    # model returns an empty array → every rec falls back deterministically
    enh = enhance_report(report, sig, snap, Settings(),
                         client=_FakeClient("[]"))
    assert len(enh.items) == len(report.recommendations)
    assert all(not i.narrative_from_llm for i in enh.items)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all llm tests passed")
