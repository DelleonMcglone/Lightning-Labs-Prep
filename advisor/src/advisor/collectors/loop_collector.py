"""Loop market collector (SPEC FR3).

Talks to a running ``loopd`` over its REST API (the grpc-gateway mirror of
looprpc — see repo-reviews/lnd.md §3d for the pattern). Auth follows lnd
conventions: TLS cert as the CA, macaroon hex in the
``Grpc-Metadata-macaroon`` header.

Degrades gracefully: any failure returns ``connected=False``.
"""

from __future__ import annotations

import codecs
from pathlib import Path
from typing import Optional

import requests

from ..models import LoopMarket, LoopQuote


def parse_out_quote(payload: dict, amount_sat: int) -> LoopQuote:
    return LoopQuote(
        amount_sat=amount_sat,
        swap_fee_sat=int(payload.get("swap_fee_sat", 0)),
        miner_fee_sat=int(payload.get("htlc_sweep_fee_sat", 0)),
        prepay_sat=int(payload.get("prepay_amt_sat", 0)),
    )


def parse_in_quote(payload: dict, amount_sat: int) -> LoopQuote:
    return LoopQuote(
        amount_sat=amount_sat,
        swap_fee_sat=int(payload.get("swap_fee_sat", 0)),
        miner_fee_sat=int(payload.get("htlc_publish_fee_sat", 0)),
        prepay_sat=0,  # loop in has no prepay
    )


class _LoopRest:
    def __init__(self, host: str, loop_dir: Path, network: str,
                 timeout: float = 15.0):
        base_dir = Path(loop_dir) / network
        self.base = f"https://{host}"
        self.verify = str(base_dir / "tls.cert")
        mac_path = base_dir / "loop.macaroon"
        self.headers = {}
        if mac_path.exists():
            self.headers["Grpc-Metadata-macaroon"] = codecs.encode(
                mac_path.read_bytes(), "hex"
            ).decode()
        self.timeout = timeout

    def get(self, path: str) -> Optional[dict]:
        try:
            resp = requests.get(
                f"{self.base}{path}",
                headers=self.headers,
                verify=self.verify,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None


def collect_loop_market(
    host: str, loop_dir: Path, network: str, quote_amount_sat: int
) -> LoopMarket:
    """Query terms + quotes from a running loopd; never raises."""
    rest = _LoopRest(host, loop_dir, network)

    out_terms = rest.get("/v1/loop/out/terms")
    if out_terms is None:
        return LoopMarket(connected=False)
    in_terms = rest.get("/v1/loop/in/terms") or {}

    amt = quote_amount_sat
    out_q = rest.get(f"/v1/loop/out/quote/{amt}")
    in_q = rest.get(f"/v1/loop/in/quote/{amt}")

    return LoopMarket(
        connected=True,
        out_min_sat=int(out_terms.get("min_swap_amount", 0)),
        out_max_sat=int(out_terms.get("max_swap_amount", 0)),
        in_min_sat=int(in_terms.get("min_swap_amount", 0)),
        in_max_sat=int(in_terms.get("max_swap_amount", 0)),
        out_quote=parse_out_quote(out_q, amt) if out_q else None,
        in_quote=parse_in_quote(in_q, amt) if in_q else None,
    )
