# Decision heuristics

Prioritization judgment distilled from the source reviews and live sessions.
These guide *ranking and framing*, not arithmetic.

## Prioritization

1. **Receive-failure risk first.** For a receiving node, low inbound headroom
   outranks every optimization — failures are silent and cost customers
   (00-liquidity-concepts). Urgent even when nothing looks broken.
2. **Cheap and reversible before expensive and final.** Fee retune (R5) before
   rebalance (R4) before close (R3). A close is irreversible and burns a chain
   fee; a policy update is free.
3. **Top-3 rule.** Surface at most three recommendations by default; an
   overwhelmed operator does nothing (Persona C). Everything else goes behind
   a "show all".

## Market interpretation

4. **Depth ≠ liquidity.** Resting orders don't mean fills — testnet Pool has
   had depth but no cleared batch since May 2023. Estimate *fill probability*
   from recent batch history before recommending a resting order; prefer Loop
   (immediate execution) when fill probability is low and need is urgent.
5. **A price is a (rate, fee-environment) pair.** Never recommend a Pool rate
   without a matched `max_batch_feerate`, and check it against the
   auctioneer's announced next-batch fee rate.
6. **Statistical relativity beats magic numbers.** Judge channels against the
   node's own portfolio (IQR), not absolute cutoffs — Faraday's core lesson.
   Corollary: with < ~5 comparable channels, outlier flags are weak evidence;
   say so rather than overclaiming.

## Cost reasoning

7. **Fixed costs dominate small actions.** Both Pool and Loop are mostly
   fixed-cost at small size; consolidate (R7) and batch actions. If an action
   is under ~250k sats, question whether it should happen at all.
8. **When acquiring inbound, direction of error matters.** Slightly too much
   inbound is cheap insurance; running dry is a customer-facing failure. Round
   up for receivers.
9. **Defer is a real recommendation.** "Do nothing until fees drop" (R6) is
   often the highest-value advice; always compute the savings so the wait has
   a number attached.

## Trust framing

10. **Explain the why in seesaw terms.** Operators act on recommendations they
    understand; one sentence of mechanism ("this channel is 95% on your side,
    so you can't receive through it") beats jargon.
11. **Show the escape hatch.** Non-custodial tools always have one (account
    expiry, timeout path, cooperative close). Mentioning it builds warranted
    trust.
12. **Never overstate certainty.** Signals from short windows (young channels,
    <30d history) get hedged language and lower rank.
