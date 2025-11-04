import requests
import zoneinfo

def get_sunrise(lat,long,tz):
    url = "https://api.sunrise-sunset.org/json"
    params = {
        "lat": lat,
        "lng": long,
        "tzid": tz,
        "formatted": 0  # ISO 8601 output
    }

    response = requests.get(url, params, timeout=10)
    response.raise_for_status()
    data = response.json()
    # data["results"]["sunrise"] is ISO string
    return data["results"]["sunrise"]


def get_timezone_from_coords(lat, lng):
    res = requests.get(f"https://timeapi.io/api/TimeZone/coordinate?latitude={lat}&longitude={lng}")
    res.raise_for_status()
    return res.json()["timeZone"]

def get_coords_from_ip():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    res = requests.get("https://ipapi.co/json/", headers=headers, timeout=10)
    res.raise_for_status()
    data = res.json()
    return data["latitude"], data["longitude"]

if __name__ == "__main__":
    lat, lng = get_coords_from_ip()
    tz_name = get_timezone_from_coords(lat, lng)
    tz = zoneinfo.ZoneInfo(tz_name)
    sunrise_iso = get_sunrise(lat, lng, f"{tz}")
    print(f"Sunrise at: {sunrise_iso}, Your timezone: {tz}")