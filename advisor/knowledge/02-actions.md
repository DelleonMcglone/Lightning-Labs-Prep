# Action catalog (R1–R7)

The recommendation types the engine can emit (SPEC §5), with when-to-use and
command templates. The engine fills in all numbers; placeholders here are
`<angle-bracketed>`.

## R1 — Acquire inbound

- **When**: inbound headroom low relative to receive needs (merchant profile),
  or inbound share of capacity far below purpose-appropriate level.
- **Options (always price both, see 01-economics)**:
  - Loop Out: `loop out --amt <sats> --channel <chan_id> --conf_target <n>`
  - Pool bid: `pool orders submit bid --amt <sats> --interest_rate_percent <pct>
    --lease_duration_blocks <blocks> --max_batch_fee_rate <sat_per_vb>
    --acct_key <key>`
- **Risks**: Loop Out needs ≥ server minimum (250k observed) and routable
  outbound; Pool bid may rest unfilled (testnet market is dormant; mainnet
  varies) and needs a funded account.

## R2 — Acquire outbound

- **When**: outbound depleted; node can't send or route out.
- **Options**: Loop In (`loop in --amt <sats>`), or open a channel
  (`lncli openchannel <pubkey> <sats> --sat_per_vbyte <rate>`).
- **Note**: Loop In is the cheap direction (client publishes the HTLC).

## R3 — Close underperforming channel

- **When**: channel is a **lower IQR outlier** on revenue/volume per
  capacity-day vs. the node's other channels, AND old enough to judge, AND
  chain fees are reasonable (else defer via R6).
- **Command**: `lncli closechannel <funding_txid> <output_index>`
- **Risks**: closing costs a chain fee now and the reserve; capital is only
  redeployable after confirmation. Never close the only channel.

## R4 — Rebalance a channel

- **When**: channel one-sided but the peer routes well (good uptime/history) —
  worth keeping, just re-centered.
- **Options**: circular self-payment via a rebalance tool, or Loop to shift
  balance (out of the full side / into the empty side).
- **Rule**: rebalancing cost must be < the value of restored bidirectional
  routing; otherwise leave it.

## R5 — Retune routing fees

- **When**: channel drains instantly (fee too low) or never forwards despite a
  good position (fee too high).
- **Command**: `lncli updatechanpolicy --base_fee_msat <n> --fee_rate_ppm <n>
  --chan_point <cp>`
- **Note**: cheap, reversible, first thing to try before R3/R4 on a
  well-connected peer.

## R6 — Defer on-chain action

- **When**: any recommendation involving a chain transaction (R1-Pool/Loop,
  R2, R3) while mempool fees are elevated vs. recent baseline.
- **Output**: "wait — this action costs <X> now vs ≈<Y> at <target> sat/vB;
  savings <Z> sats". Urgency can override (e.g. imminent receive failure).

## R7 — Consolidate small Pool orders

- **When**: multiple small resting orders whose per-order chain footprint
  pushes each below breakeven in the current fee regime.
- **Action**: cancel small orders, submit one larger order (same total).
- **Why**: breakeven scales with 1/(amount × duration) — one 1M-sat order has
  10× better fixed-cost amortization than ten 100k orders.
