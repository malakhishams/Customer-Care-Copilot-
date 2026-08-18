"""
DB Tool — Order Lookup (US-01)

Pure functions, no LangGraph dependency. Given an order_id or an email,
returns the matching order record (joined with CustomerContacts and
Shipments), or a clean "not found" result. Never raises on missing data —
the caller decides how to phrase the fallback message (robustness requirement).
"""

import sqlite3
from typing import Optional

DB_PATH = r"data\northwind.db"

# returned dict has a stable, predictable shape for downstream nodes.
ORDER_SELECT = """
    SELECT
        o.OrderID,
        o.CustomerID,
        cc.Email,
        o.OrderDate,
        o.RequiredDate,
        o.ShippedDate,
        o.ShipName,
        o.ShipCity,
        o.ShipCountry,
        s.Carrier,
        s.TrackingNumber
    FROM Orders o
    LEFT JOIN CustomerContacts cc ON o.CustomerID = cc.CustomerID
    LEFT JOIN Shipments s ON o.OrderID = s.OrderID
"""

COLUMN_NAMES = [
    "order_id", "customer_id", "email", "order_date", "required_date",
    "shipped_date", "ship_name", "ship_city", "ship_country",
    "carrier", "tracking_number",
]


def _row_to_dict(row: tuple) -> dict:
    return dict(zip(COLUMN_NAMES, row))


def lookup_order_by_id(order_id: str) -> Optional[dict]:
    """Returns the order record for an exact OrderID match, or None if not found."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"{ORDER_SELECT} WHERE o.OrderID = ?;", (order_id,))
    row = cursor.fetchone()
    conn.close()

    return _row_to_dict(row) if row else None


def lookup_order_by_email(email: str) -> Optional[dict]:
    """
    Returns the customer's MOST RECENT order for the given email, or None
    if the email matches no customer / no orders.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"{ORDER_SELECT} WHERE cc.Email = ? ORDER BY o.OrderDate DESC LIMIT 1;",
        (email,),
    )
    row = cursor.fetchone()
    conn.close()

    return _row_to_dict(row) if row else None


def lookup_order(order_id: Optional[str] = None, email: Optional[str] = None) -> dict:
    """
    Main entry point for the Order Lookup node. Tries order_id first (more
    specific), falls back to email. Always returns a dict with a `found`
    flag so the caller never has to guard against None.
    """
    record = None

    if order_id:
        record = lookup_order_by_id(order_id)
    if record is None and email:
        record = lookup_order_by_email(email)

    if record is None:
        return {"found": False, "order": None}

    return {"found": True, "order": record}


if __name__ == "__main__":
    # Quick manual test
    print("By order_id:", lookup_order(order_id="10248"))
    print("By email:", lookup_order(email="vinet@example-customer.com"))
    print("Not found:", lookup_order(order_id="99999999"))