"""Read-only Base JSON-RPC helpers.

These calls only *read* Base (mainnet chain id 8453 / Base Sepolia 84532).
They need no wallet, no key, and can never move funds. They exist so the
agent can (a) prove it is looking at the right network before it reasons
about B20 tokenized stocks, and (b) optionally read a wallet's ERC-20
``balanceOf`` for position sync -- the same standard call that underlies
the B20 ``balanceOfUI`` share-equivalent view once the API multiplier is
applied.
"""
from __future__ import annotations

import json
import urllib.request
from decimal import Decimal
from typing import Any, Callable, Optional

DEFAULT_BASE_RPC = "https://mainnet.base.org"
BASE_MAINNET_CHAIN_ID = 8453

Transport = Callable[[str, dict[str, Any]], Any]


def http_transport(url: str, payload: dict[str, Any], timeout: float = 8.0) -> Any:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class BaseChainReader:
    def __init__(self, rpc_url: str = DEFAULT_BASE_RPC, transport: Transport = http_transport):
        self.rpc_url = rpc_url
        self.transport = transport
        self._counter = 0

    def _rpc(self, method: str, params: list[Any]) -> Any:
        self._counter += 1
        response = self.transport(
            self.rpc_url,
            {"jsonrpc": "2.0", "id": self._counter, "method": method, "params": params},
        )
        if isinstance(response, dict) and response.get("error"):
            raise RuntimeError(f"RPC error for {method}: {response['error']}")
        return response.get("result") if isinstance(response, dict) else None

    def chain_id(self) -> int:
        return int(self._rpc("eth_chainId", []), 16)

    def block_number(self) -> int:
        return int(self._rpc("eth_blockNumber", []), 16)

    def health(self) -> dict[str, Any]:
        """Network identity check. Never raises: reports unavailability."""
        try:
            chain_id = self.chain_id()
            return {
                "rpc_url": self.rpc_url,
                "reachable": True,
                "chain_id": chain_id,
                "is_base_mainnet": chain_id == BASE_MAINNET_CHAIN_ID,
                "block_number": self.block_number(),
            }
        except Exception as exc:  # network down is a reportable state, not a crash
            return {"rpc_url": self.rpc_url, "reachable": False, "error": str(exc)}

    def erc20_balance_of(self, token_address: str, wallet_address: str) -> int:
        """Raw ERC-20 balanceOf (smallest units) via eth_call. Read-only."""
        selector = "0x70a08231"  # balanceOf(address)
        argument = wallet_address.lower().replace("0x", "").rjust(64, "0")
        result = self._rpc(
            "eth_call",
            [{"to": token_address, "data": selector + argument}, "latest"],
        )
        return int(result, 16)

    def token_position(
        self, token_address: str, wallet_address: str, decimals: int, multiplier: Decimal
    ) -> dict[str, Any]:
        """Wallet position in token units and share-equivalents (x multiplier)."""
        raw = self.erc20_balance_of(token_address, wallet_address)
        token_units = Decimal(raw) / (Decimal(10) ** decimals)
        return {
            "token_address": token_address,
            "wallet": wallet_address,
            "token_quantity": str(token_units),
            "share_equivalents": str(token_units * multiplier),
        }
