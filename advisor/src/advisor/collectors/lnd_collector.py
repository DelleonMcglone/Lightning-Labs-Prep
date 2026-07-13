"""Build a NodeSnapshot from lnd's read RPCs (M0/M1 collector, SPEC FR2)."""

from __future__ import annotations

import time

from ..lndclient import LndClient
from ..models import (
    Balances,
    ChannelState,
    ForwardingStats,
    NodeIdentity,
    NodeSnapshot,
)

FORWARDING_LOOKBACK_DAYS = 30


def _collect_forwarding(client: LndClient, days: int) -> dict:
    """Aggregate forwarding events per channel over the lookback window.

    Fees are attributed to the *outgoing* channel (where they are earned).
    """
    now = int(time.time())
    events = client.forwarding_history(now - days * 86_400, now)
    stats: dict = {}

    def _get(chan_id: int) -> ForwardingStats:
        if chan_id not in stats:
            stats[chan_id] = ForwardingStats(chan_id=chan_id)
        return stats[chan_id]

    for ev in events:
        fin = _get(ev.chan_id_in)
        fin.events_in += 1
        fin.amt_in_sat += ev.amt_in
        fout = _get(ev.chan_id_out)
        fout.events_out += 1
        fout.amt_out_sat += ev.amt_out
        fout.fee_msat += ev.fee_msat

    return stats


def collect_snapshot(client: LndClient) -> NodeSnapshot:
    """Query lnd and normalize the result into a typed NodeSnapshot."""
    info = client.get_info()
    channels = client.list_channels()
    wallet = client.wallet_balance()
    chan_bal = client.channel_balance()
    forwarding = _collect_forwarding(client, FORWARDING_LOOKBACK_DAYS)

    identity = NodeIdentity(
        alias=info.alias,
        pubkey=info.identity_pubkey,
        version=info.version,
        block_height=info.block_height,
        synced_to_chain=info.synced_to_chain,
        num_active_channels=info.num_active_channels,
        num_peers=info.num_peers,
    )

    balances = Balances(
        onchain_confirmed=wallet.confirmed_balance,
        onchain_unconfirmed=wallet.unconfirmed_balance,
        ln_local=chan_bal.local_balance.sat,
        ln_remote=chan_bal.remote_balance.sat,
    )

    channel_states = [
        ChannelState(
            chan_point=c.channel_point,
            chan_id=c.chan_id,
            peer_pubkey=c.remote_pubkey,
            capacity_sat=c.capacity,
            local_sat=c.local_balance,
            remote_sat=c.remote_balance,
            active=c.active,
            private=c.private,
            uptime_s=c.uptime,
            lifetime_s=c.lifetime,
            total_sent_sat=c.total_satoshis_sent,
            total_received_sat=c.total_satoshis_received,
        )
        for c in channels.channels
    ]

    return NodeSnapshot(
        identity=identity,
        balances=balances,
        channels=channel_states,
        forwarding=forwarding,
        forwarding_lookback_days=FORWARDING_LOOKBACK_DAYS,
    )
