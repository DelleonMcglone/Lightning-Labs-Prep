# Economics — the formulas

Relationships the engine computes and the LLM may reference by name. The LLM
never evaluates these itself (SPEC NFR4).
Sources: [04 — Pool auctions & lease pricing](../../04-pool-auctions-lease-pricing.md),
[05 — Pool observations](../../05-pool-observations.md),
[Loop review §5](../../repo-reviews/loop.md).

## Pool lease pricing

- Rate unit: **ppb per block** (parts-per-billion of the leased amount).
- Premium: `premium_sats = amount_sats × rate_ppb × duration_blocks / 1e9`
- Annualize (~52,560 blocks/yr): `APR ≈ rate_ppb × 52,560 / 1e9`
  - 500 ppb ≈ 2.6% · 1,000 ppb ≈ 5.26% · 2,000 ppb ≈ 10.5%
- Orders are quantized in **100k-sat units**; min account 100k sats.
- Execution fee (testnet observed): 1 sat base + 1,000 ppm per side.

## The chain-fee breakeven floor (the key structural fact)

Each batch participant pays a roughly **fixed** on-chain footprint
(~350 vbytes), independent of lease size, so the breakeven lease rate scales
**inversely with amount × duration**:

`breakeven_ppb ≈ chain_cost_sats / (amount_sats × duration_blocks) × 1e9`

Consequences:
- When mempool fees rise, clearing rates must rise; **small/short leases get
  priced out entirely**.
- Bigger/longer is a lever: 20× the amount barely moves total cost.
- An order is only viable if its economics clear **at the fee rate the batch
  will pay** — hence `max_batch_feerate` is part of the decision, not an
  afterthought.

## Loop swap costs (empirical shape, testnet-verified)

- Fee model: `fee = base + amount × rate/1e6` (ppm) **plus** on-chain
  miner-fee components that dominate at small sizes.
- **Loop In is ~10× cheaper than Loop Out** at the same size (observed 0.19%
  vs 1.83% at 500k), because in Loop In the client publishes the on-chain
  HTLC; in Loop Out the server publishes and the client also sweeps.
- Loop Out has a **prepay** (no-show fee) — small, non-refundable.
- Fee scales sub-linearly with amount: mostly fixed cost (observed 250k→5M:
  fee only ×1.5).

## Comparison rule for acquiring inbound (R1)

Inbound can be manufactured two ways; always price both:
- **Loop Out**: cost = swap fee + prepay + on-chain sweep; instant-ish; uses
  existing channel balance; no term guarantee.
- **Pool bid**: cost = premium + exec fee + chain footprint; delivers a **new
  leased channel** with a script-enforced term; needs a funded Pool account.

Normalize both to **sats per sat-of-inbound (and per block of duration if a
term matters)** before comparing.
