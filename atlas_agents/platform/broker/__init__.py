"""Broker integration agent utilities."""

from __future__ import annotations

from typing import Any


def normalize_position(row: dict[str, Any]) -> dict[str, Any]:
    qty = float(row.get("qty", row.get("quantity", 0)) or 0)
    price = float(row.get("market_price", row.get("price", 0)) or 0)
    return {
        "symbol": str(row.get("symbol", "")).upper(),
        "qty": qty,
        "market_price": price,
        "market_value": round(qty * price, 2),
        "asset_class": row.get("asset_class", "equity"),
    }


def positions_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positions = [normalize_position(r) for r in rows]
    return {"positions": positions, "total_value": round(sum(p["market_value"] for p in positions), 2)}
