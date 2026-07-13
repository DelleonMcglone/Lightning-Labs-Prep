# Advisor knowledge base

Curated domain knowledge the LLM advisor (SPEC M4) loads as context when
prioritizing and explaining recommendations. This is the **judgment layer's
textbook** — the numbers themselves always come from the deterministic engine
(SPEC NFR4), never from here.

## Structure

| File | Contents | Used for |
| --- | --- | --- |
| [00-liquidity-concepts.md](./00-liquidity-concepts.md) | Inbound/outbound, the channel seesaw, why new nodes can't receive | Explaining *why* a recommendation matters, in operator language |
| [01-economics.md](./01-economics.md) | The formulas: ppb↔APR, lease premium, breakeven floor, Loop fee model | Sanity vocabulary — the LLM references these; the engine computes them |
| [02-actions.md](./02-actions.md) | The R1–R7 action catalog: when each applies, its command template, its risks | Mapping engine output to operator instructions |
| [03-heuristics.md](./03-heuristics.md) | Decision rules-of-thumb distilled from the source reviews and live sessions | Prioritization judgment |

## Rules for content

1. **No live numbers.** Anything that changes (rates, fees, quotes) belongs in
   collectors, not here. This corpus holds *relationships and rules*, not data.
2. **Every claim traceable.** Facts here are distilled from the study notes and
   source reviews in the parent repo (notes 01–05, repo-reviews/) — each file
   links its sources.
3. **Written for injection.** Files are small and self-contained; M4 loads them
   into the prompt wholesale. Keep each under ~150 lines.

## Provenance

Distilled from: [03 — Lightning Liquidity](../../03-lightning-liquidity.md) ·
[04 — Pool auctions & lease pricing](../../04-pool-auctions-lease-pricing.md) ·
[05 — Pool observations](../../05-pool-observations.md) ·
[repo reviews](../../repo-reviews/) (Pool, LND, Loop, Faraday).
