"""
geocode.py — Pincode enrichment using the free PostalPincode API.

Endpoint: GET https://api.postalpincode.in/pincode/{PINCODE}
No authentication required. Returns District + State for any Indian pincode.

Usage:
    from geocode import enrich_location
    location = enrich_location("242307,Sahkari Chini Mills Ltd Tilhar Shahjahanpur")
    # → "242307,Sahkari Chini Mills Ltd Tilhar Shahjahanpur | Shahjahanpur, Uttar Pradesh"
"""

import re
import json
import urllib.request
import urllib.error

# In-process cache: pincode → (district, state) or None on failure
_cache: dict = {}

_API_URL = "https://api.postalpincode.in/pincode/{pin}"
_TIMEOUT  = 4   # seconds — keep UI-responsive


def lookup_pincode(pin: str) -> tuple[str, str] | None:
    """
    Look up a 6-digit Indian pincode.
    Returns (district, state) on success, None on failure.
    Results are cached for the lifetime of the process.
    """
    pin = pin.strip()
    if pin in _cache:
        return _cache[pin]

    try:
        url = _API_URL.format(pin=pin)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "TenderTracker/1.0"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if (
            isinstance(data, list)
            and data
            and data[0].get("Status") == "Success"
            and data[0].get("PostOffice")
        ):
            po = data[0]["PostOffice"][0]
            result = (po.get("District", ""), po.get("State", ""))
            _cache[pin] = result
            return result

    except Exception:
        pass   # network down, invalid pin, timeout — degrade silently

    _cache[pin] = None
    return None


def enrich_location(location: str) -> str:
    """
    Given a raw location string (as extracted from the PDF), append
    "District, State" from the PostalPincode API if:
      • A 6-digit pincode is found in the string, AND
      • The district / state are not already present (case-insensitive check).

    Returns the enriched string, or the original if no pincode or lookup fails.
    """
    if not location:
        return location

    pin_m = re.search(r'\b(\d{6})\b', location)
    if not pin_m:
        return location

    pin = pin_m.group(1)
    result = lookup_pincode(pin)
    if not result:
        return location

    district, state = result
    loc_lower = location.lower()

    # Only append if both district and state aren't already mentioned
    district_present = district and district.lower() in loc_lower
    state_present    = state    and state.lower()    in loc_lower

    if district_present and state_present:
        return location

    parts = []
    if district and not district_present:
        parts.append(district)
    if state and not state_present:
        parts.append(state)

    if parts:
        return f"{location} | {', '.join(parts)}"

    return location
