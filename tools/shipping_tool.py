"""
Shipping Tool — Tracking (US-02)

Wraps Shippo's tracking endpoint (test mode). Given a carrier + tracking
number, returns the current status + an "evidence snippet" (latest status
+ timestamp) the customer/agent can trust.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SHIPPO_API_URL = "https://api.goshippo.com/tracks/"
SHIPPO_API_KEY = os.getenv("SHIPPO_API_KEY")


def get_tracking_status(carrier: str, tracking_number: str) -> dict:
    """
    Calls Shippo's tracking endpoint. Always returns a dict with an
    `available` flag so callers never have to guard against exceptions.

    On success:
      {"available": True, "status": "TRANSIT", "status_details": "...",
       "status_date": "...", "eta": "..."}
    On failure (network error, bad response, missing key):
      {"available": False, "error": "<reason>"}
    """
    if not SHIPPO_API_KEY:
        return {"available": False, "error": "Shippo API key not configured"}

    headers = {"Authorization": f"ShippoToken {SHIPPO_API_KEY}"}
    payload = {"carrier": carrier, "tracking_number": tracking_number}

    try:
        response = requests.post(SHIPPO_API_URL, headers=headers, data=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        return {"available": False, "error": f"Network error: {e}"}

    if response.status_code != 200:
        return {"available": False, "error": f"Shippo returned status {response.status_code}"}

    data = response.json()
    tracking_status = data.get("tracking_status") or {}

    return {
        "available": True,
        "status": tracking_status.get("status", "UNKNOWN"),
        "status_details": tracking_status.get("status_details", ""),
        "status_date": tracking_status.get("status_date", ""),
        "eta": data.get("eta", ""),
    }


if __name__ == "__main__":
    print("In transit:", get_tracking_status("shippo", "SHIPPO_TRANSIT"))
    print("Delivered:", get_tracking_status("shippo", "SHIPPO_DELIVERED"))
    print("Bad carrier (should fail gracefully):", get_tracking_status("fake_carrier", "12345"))