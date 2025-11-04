import requests
import zoneinfo
from flask import Flask, jsonify, request, abort
import os



app = Flask(__name__)
TOKEN = os.getenv("AUTH_TOKEN")

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

#def get_coords_from_ip():
#    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
#    res = requests.get("https://ipapi.co/json/", headers=headers, timeout=10)
#    res.raise_for_status()
#    data = res.json()
#    return data["latitude"], data["longitude"]

#lat, lng = get_coords_from_ip() #used for dynamic location finding
lat, lng = 61.49911,23.78712 #Hardcoded coordinates for Tampere due to the VM I am deploying to being in the United States.
tz_name = get_timezone_from_coords(lat, lng)
tz = zoneinfo.ZoneInfo(tz_name) 

@app.route("/api/v1/sunrise", methods=["GET"])
def sunrise():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        abort(401)
    token = auth.split(None, 1)[1]
    if token != TOKEN:
        abort(401)

    data = get_sunrise(lat, lng, f"{tz}")
    print(f"Sunrise at: {data}, Your timezone: {tz}")
    return jsonify({"sunrise": data})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)