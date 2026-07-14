# Demo walkthrough (5 minutes)

Script for the MVP demo video. Everything below runs against the local
testnet stack (`lnd` + `poold` + `loopd`) — real daemons, real market data,
no funds at risk.

## Setup (before recording)

```bash
cd advisor && . .venv/bin/activate
# lnd (testnet) running + unlocked; poold + loopd running (see setup/)
# ANTHROPIC_API_KEY in advisor/.env for the LLM layer + chat
```

## 1 — The problem (30s)

"Lightning node operators struggle to know when and how to manage channel
liquidity." Show it:

```bash
advisor snapshot
```

Point at the seesaw: this node has almost no inbound — customers literally
cannot pay it, and nothing in a normal node UI says so.

## 2 — Deterministic signals (45s)

```bash
advisor signals
```

Per-channel balance/uptime/routing metrics, Faraday-style IQR outlier flags,
honest exclusions ("monitored < 24h"). Emphasize: pure code, unit-tested,
no AI anywhere yet.

## 3 — The market, live (45s)

```bash
advisor market
```

Live mempool fees, the real Pool auction (clearing rate → APR), real Loop
quotes. Call out Loop In vs Loop Out asymmetry and the next-batch fee rate.

## 4 — Recommendations (60s)

```bash
advisor recommend --offline   # deterministic baseline
advisor recommend             # + Claude prioritization & explanation
```

The CRITICAL "acquire inbound" rec: both options priced (Loop Out honestly
infeasible), full cost decomposition, the exact command with the
(rate, max_batch_feerate) pair, caveats. Then the LLM layer: same numbers,
plain-language why. Say the line: **"the model never does arithmetic — every
figure is computed and tested; Claude only prioritizes and explains."**

## 5 — History → foresight (45s)

```bash
advisor ingest --quiet && advisor history
```

The time series, the 7-day fee baseline, the inbound trend. Mention the
runway rule: "inbound looks fine today but empties in 4 days" fires before
the failure, not after.

## 6 — The web UI (60s)

```bash
advisor serve   # http://127.0.0.1:8899
```

- Left: the seesaw, market tiles, recommendation cards (copy the command).
- Right: chat — ask "Why can't my node receive payments?" and "What would
  you do first, and what does it cost?" Point out commands are quoted
  verbatim from the engine, chat is labeled conversational, cards stay
  authoritative.

## 7 — Safety close (15s)

Read-only macaroon, recommend-only, privacy filter on every prompt, offline
mode always available. "It can tell you what to do; it cannot touch your
funds."

---

Total: ~5 min. Recorded output examples live in the repo history if a
retake needs reference numbers.
