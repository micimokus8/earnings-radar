from __future__ import annotations

import xml.etree.ElementTree as ET


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_form4_xml(xml_text: str) -> list[dict]:
    """Parse ownership transactions without treating every Form 4 as a sale."""
    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, TypeError) as exc:
        raise ValueError("invalid Form 4 XML") from exc

    transactions = []
    for transaction in root.iter():
        if _local_name(transaction.tag) not in {
            "nonDerivativeTransaction",
            "derivativeTransaction",
        }:
            continue
        code = None
        shares = None
        for node in transaction.iter():
            name = _local_name(node.tag)
            if name == "transactionCode" and node.text:
                code = node.text.strip().upper()
            elif name == "value" and node.text and shares is None:
                try:
                    shares = float(node.text.strip())
                except ValueError:
                    shares = None
        if code:
            transactions.append({"code": code, "shares": shares})
    return transactions


def summarize_transactions(transactions: list[dict]) -> dict:
    codes = [item["code"] for item in transactions]
    sell_shares = sum(
        item.get("shares") or 0 for item in transactions if item.get("code") == "S"
    )
    return {
        "status": "SELL_FLAG" if sell_shares > 0 else "NO_DIRECT_SELL",
        "sell_flag": sell_shares > 0,
        "sell_shares": sell_shares,
        "codes": codes,
    }
