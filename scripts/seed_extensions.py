"""
Extends the Northwind SQLite DB with two companion tables that don't exist
in the original schema but are required by the Customer Care Copilot:

  1. CustomerContacts  (CustomerID -> Email)
     Northwind's CustomerID is a company code (e.g. "VINET"), not something
     a real customer would type in. We synthesize a plausible email per
     customer so US-01 ("collect email/order ID") has something real to check.

  2. Shipments  (OrderID -> TrackingNumber, Carrier)
     Northwind has no tracking data at all. We assign a Shippo TEST-MODE
     mock tracking number (SHIPPO_TRANSIT, SHIPPO_DELIVERED, etc.) to every
     shipped order, cycling through the values so your demo can show
     different tracking statuses (US-02).

This is intentionally additive: it does NOT touch the original Orders,
Customers, or Order Details tables. Safe to re-run (idempotent).

Run from your project root:
    python seed_extensions.py
"""

import sqlite3

DB_PATH = r"\data\northwind.db"

# Shippo test-mode mock tracking values (carrier must be "shippo" in test mode)
MOCK_TRACKING_STATUSES = [
    "SHIPPO_TRANSIT",
    "SHIPPO_DELIVERED",
    "SHIPPO_PRE_TRANSIT",
    "SHIPPO_RETURNED",
    "SHIPPO_UNKNOWN",
    "SHIPPO_FAILURE",
]


def create_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS CustomerContacts (
            CustomerID TEXT PRIMARY KEY,
            Email TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Shipments (
            OrderID INTEGER PRIMARY KEY,
            Carrier TEXT NOT NULL,
            TrackingNumber TEXT NOT NULL,
            FOREIGN KEY (OrderID) REFERENCES Orders(OrderID)
        );
    """)


def seed_customer_contacts(cursor):
    cursor.execute("SELECT DISTINCT CustomerID FROM Orders;")
    customer_ids = [row[0] for row in cursor.fetchall()]

    for cid in customer_ids:
        email = f"{cid.lower()}@example-customer.com"
        cursor.execute(
            "INSERT OR REPLACE INTO CustomerContacts (CustomerID, Email) VALUES (?, ?);",
            (cid, email),
        )
    print(f"[OK] Seeded {len(customer_ids)} customer emails into CustomerContacts.")


def seed_shipments(cursor):
    # Only orders that have actually shipped get a tracking number —
    # this also gives you a natural "no tracking yet" case to handle (US-02 fallback).
    cursor.execute("SELECT OrderID FROM Orders WHERE ShippedDate IS NOT NULL;")
    shipped_order_ids = [row[0] for row in cursor.fetchall()]

    for i, order_id in enumerate(shipped_order_ids):
        tracking_number = MOCK_TRACKING_STATUSES[i % len(MOCK_TRACKING_STATUSES)]
        cursor.execute(
            "INSERT OR REPLACE INTO Shipments (OrderID, Carrier, TrackingNumber) VALUES (?, ?, ?);",
            (order_id, "shippo", tracking_number),
        )
    print(f"[OK] Seeded {len(shipped_order_ids)} shipments into Shipments table.")


def sanity_print(cursor):
    print("\n--- Sample joined record ---")
    cursor.execute("""
        SELECT o.OrderID, o.CustomerID, cc.Email, s.Carrier, s.TrackingNumber
        FROM Orders o
        LEFT JOIN CustomerContacts cc ON o.CustomerID = cc.CustomerID
        LEFT JOIN Shipments s ON o.OrderID = s.OrderID
        LIMIT 3;
    """)
    for row in cursor.fetchall():
        print(row)


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    create_tables(cursor)
    seed_customer_contacts(cursor)
    seed_shipments(cursor)
    conn.commit()

    sanity_print(cursor)
    conn.close()
    print("\n[DONE] Northwind DB extended successfully.")