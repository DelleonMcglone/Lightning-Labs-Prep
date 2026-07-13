# Liquidity concepts

Core mental model for explaining recommendations to operators.
Source: [03 — Lightning Liquidity](../../03-lightning-liquidity.md).

## The seesaw

- A channel has **fixed capacity**; it splits into **local balance (outbound —
  what you can send)** and **remote balance (inbound — what you can receive)**.
  They always sum to capacity: every sat you can send is a sat you can't
  receive.
- Payments **tip the seesaw**: sending moves balance to the remote side
  (outbound shrinks, inbound grows); receiving does the reverse.
- **Liquidity is a direction, not a balance.** A node can be rich and still
  unable to receive (all local) or unable to send (all remote).

## Why new nodes can't receive

The funder of a channel starts with all capacity on their side. A fresh node
that opened its own channels has **zero inbound** — customer payments fail
until someone commits capital *toward* it (a peer opens a channel to it, it
spends, it uses Loop Out, or it buys a lease on Pool).

## What "good" looks like, by node purpose

- **Spender**: mostly outbound; fewer, larger channels to well-connected peers;
  private channels are fine.
- **Receiver (merchant)**: mostly inbound; own balance kept low; inbound
  headroom must exceed expected receive volume between top-ups.
- **Router**: both directions in every channel; a channel that's all one side
  can only route one way and earns nothing in the other direction.

## Failure modes worth naming for operators

- **Silent receive failure**: a depleted-inbound merchant doesn't see failed
  payments — customers just leave. This is why low inbound headroom is urgent
  even though nothing looks "broken".
- **One-sided channel**: local ratio outside roughly [0.2, 0.8]. Not
  automatically bad (a receiver *wants* low local), so always interpret
  one-sidedness relative to the node's purpose.
- **Private-channel illusion**: sats in private channels look liquid to the
  wallet holding them but can't route; don't count them toward
  sending/receiving capacity.
- **Reserve**: a small slice of capacity is withheld for the future close fee;
  channels can never be fully emptied.
