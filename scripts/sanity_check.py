"""
Sanity check: confirms both external tools work BEFORE wiring them into LangGraph.
1. Opens the Northwind SQLite DB and prints one row from Orders.
2. Calls Shippo's tracking endpoint (test mode) with a mock tracking number.

Run this from your project root after activating your venv:
    python sanity_check.py
"""

import os
import sqlite3
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------- 1. Northwind SQLite check ----------
def check_northwind_db(db_path=r"\data\northwind.db"):
    print("--- Checking Northwind DB ---")
    if not os.path.exists(db_path):
        print(f"[FAIL] DB file not found at '{db_path}'. Update db_path or move the file.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Orders LIMIT 1;")
    row = cursor.fetchone()
    col_names = [desc[0] for desc in cursor.description]

    print("Columns:", col_names)
    print("Sample row:", row)
    conn.close()
    print("[OK] Northwind DB connection works.\n")


# ---------- 2. Shippo test API check ----------
def check_shippo_api():
    print("--- Checking Shippo Tracking API (test mode) ---")
    api_key = os.getenv("SHIPPO_API_KEY")
    if not api_key:
        print("[FAIL] SHIPPO_API_KEY not found in .env")
        return
    if not api_key.startswith("shippo_test_"):
        print("[WARN] Key doesn't look like a test key (should start with 'shippo_test_').")

    # Mock tracking number: carrier must be "shippo", tracking_number one of the
    # SHIPPO_* mock values (SHIPPO_TRANSIT, SHIPPO_DELIVERED, SHIPPO_RETURNED, etc.)
    url = "https://api.goshippo.com/tracks/"
    headers = {"Authorization": f"ShippoToken {api_key}"}
    payload = {
        "carrier": "shippo",
        "tracking_number": "SHIPPO_TRANSIT",
    }

    response = requests.post(url, headers=headers, data=payload)
    print("Status code:", response.status_code)
    print("Response:", response.json())

    if response.status_code == 200:
        print("[OK] Shippo test API call works.\n")
    else:
        print("[FAIL] Shippo API call did not return 200. Check your key/payload.\n")


if __name__ == "__main__":
    check_northwind_db()
    check_shippo_api()