import requests
import json
import os
import time

def get_us_diesel_price():
    """
    Returns (price_float, date_str) for the latest U.S. on-highway diesel fuel price (USD/gal)
    using EIA API v2 seriesid back-compat endpoint.
    Includes retry logic: 3 attempts with exponential delays (5s, 15s, 35s).
    """
    series_ids = [
        "PET.EMD_EPD2D_PTE_NUS_DPG.W",  # v1-style with PET. prefix + weekly suffix
        "EMD_EPD2D_PTE_NUS_DPG",        # fallback (some deployments accept bare id)
    ]

    params = {
        "api_key": "2ILtq9Ihj9D7kAwRkfzhlJPpjWvFUK2caOED3QbQ",
        "frequency": "weekly",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "offset": 0,
        "length": 1,
    }

    # Retry delays: 5s, 15s, 35s
    retry_delays = [5, 15, 35]

    last_err = None

    for sid in series_ids:  # Loop series IDs
        url = f"https://api.eia.gov/v2/seriesid/{sid}"

        for attempt in range(4):  # first try + 3 retries
            try:
                resp = requests.get(url, params=params, timeout=20)
                resp.raise_for_status()
                payload = resp.json()

                rows = payload.get("response", {}).get("data", [])
                if not rows:
                    raise RuntimeError(f"No data returned for series {sid}.")

                row = rows[0]
                period = row.get("period")
                value = float(row.get("value"))
                return value, period

            except Exception as e:
                last_err = e

                # If this was the last attempt, break to try next series_id
                if attempt >= 3:
                    print(f"[EIA] Final failure for series {sid}: {e}")
                    break

                delay = retry_delays[attempt]
                print(f"[EIA] Error fetching {sid} (attempt {attempt+1}/4). "
                      f"Retrying in {delay} seconds... Error: {e}")
                time.sleep(delay)

    # If both series IDs failed completely
    raise RuntimeError(f"EIA request failed for all series ids {series_ids}: {last_err}")


def load_surcharge_table():
    """Load surcharge table JSON from a file in the same directory as this script."""
    # Get the absolute path of the folder this .py file is in
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "fuel_table.json")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Surcharge file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_surcharge_per_mile() -> float:
    """
    Given a diesel price, loads a surcharge table from a local JSON file
    and returns the matching surcharge $/mile.
    """
    price, date = get_us_diesel_price()
    print(price)
    table = load_surcharge_table()
    price = round(float(price), 3)
    for row in table:
        if row["min"] <= price <= row["max"]:
            return row["surcharge"]

    # Optional safety: handle out-of-range prices
    if price < table[0]["min"]:
        return table[0]["surcharge"]
    if price > table[-1]["max"]:
        return table[-1]["surcharge"]
    return None
