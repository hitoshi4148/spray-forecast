import requests

def fetch_met(lat, lon):
    url = (
        "https://api.met.no/weatherapi/locationforecast/2.0/compact"
        f"?lat={lat}&lon={lon}"
    )
    headers = {
        "User-Agent": "spray-forecast/0.1 (contact: you@example.com)"
    }
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()
