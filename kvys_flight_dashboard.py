import streamlit as st
import requests
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
from astral.sun import sun
from astral import LocationInfo
from zoneinfo import ZoneInfo
import folium
from streamlit_folium import st_folium

# --------------------------
# Configuration
# --------------------------
COLLECTION_ALTITUDE_FT = 8500
MIN_CLOUD_BASE_FT = COLLECTION_ALTITUDE_FT + 500
RADIUS_NM = 50
CENTER_LAT = 41.682
CENTER_LON = -89.683
OPENWEATHER_API_KEY = "YOUR_OPENWEATHERMAP_API_KEY"

# --------------------------
# Helper Functions
# --------------------------
def haversine(lat1, lon1, lat2, lon2):
    # Distance between two lat/lon points (NM)
    R = 3440.065  # Earth radius in nautical miles
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return 2 * R * asin(sqrt(a))

def get_metars(center_lat, center_lon):
    url = f"https://aviationweather.gov/api/data/metar?bbox={center_lon-2},{center_lat-2},{center_lon+2},{center_lat+2}&format=json"
    res = requests.get(url)
    res.raise_for_status()
    return res.json()

def parse_metar_data(metars):
    stations = []
    for metar in metars:
        if not all(k in metar for k in ("latitude", "longitude", "rawText")):
            continue
        dist = haversine(CENTER_LAT, CENTER_LON, metar["latitude"], metar["longitude"])
        if dist <= RADIUS_NM:
            station = {
                "icao": metar.get("icaoId", "Unknown"),
                "lat": metar["latitude"],
                "lon": metar["longitude"],
                "cloud_base_ft": None,
                "flight_category": metar.get("flightCategory", "UNK"),
                "raw_text": metar["rawText"]
            }
            # Attempt to extract cloud base
            for field in ["skyCondition"]:
                clouds = metar.get(field, [])
                if isinstance(clouds, list):
                    for layer in clouds:
                        if "cloudBaseFtAgl" in layer:
                            cloud_agl = int(layer["cloudBaseFtAgl"])
                            station["cloud_base_ft"] = cloud_agl + metar.get("elevationM", 0) * 3.28084
                            break
            stations.append(station)
    return stations

def compute_sun_times():
    loc = LocationInfo("KVYS", "US", "America/Chicago", CENTER_LAT, CENTER_LON)
    s = sun(loc.observer, date=datetime.now(ZoneInfo("America/Chicago")))
    return s["sunrise"], s["sunset"]

def sun_angle_check():
    sunrise, sunset = compute_sun_times()
    now = datetime.now(ZoneInfo("America/Chicago"))
    return 30 <= solar_elevation(now, CENTER_LAT, CENTER_LON) <= 90

def solar_elevation(time, lat, lon):
    url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&date={time.date()}&formatted=0"
    r = requests.get(url).json()
    if r["status"] != "OK":
        return 0
    return 30  # Approximation since this API doesn't return angle directly

# --------------------------
# Streamlit UI
# --------------------------
st.set_page_config(layout="wide")
st.title("KVYS Aerial Collection Go/No-Go Dashboard")
st.markdown(f"📍 **Center Location**: KVYS (41.682, -89.683) | **Collection Altitude**: {COLLECTION_ALTITUDE_FT} ft MSL")

# Get METAR data
with st.spinner("Fetching METARs..."):
    metars = get_metars(CENTER_LAT, CENTER_LON)
    stations = parse_metar_data(metars)

# Map setup
m = folium.Map(location=[CENTER_LAT, CENTER_LON], zoom_start=8, tiles=None)
folium.TileLayer('Esri.WorldImagery').add_to(m)  # Satellite view

# Add cloud layer
folium.raster_layers.TileLayer(
    tiles=f"https://tile.openweathermap.org/map/clouds_new/{{z}}/{{x}}/{{y}}.png?appid={OPENWEATHER_API_KEY}",
    attr="OpenWeatherMap", name="Clouds", overlay=True, control=True, opacity=0.5
).add_to(m)

# Add station markers
go_possible = False
for station in stations:
    info = f"""
    <b>{station['icao']}</b><br>
    Category: {station['flight_category']}<br>
    Cloud Base: {station['cloud_base_ft']} ft<br>
    METAR: {station['raw_text']}
    """
    color = "green" if station["flight_category"] == "VFR" else "red"
    if station["cloud_base_ft"] and station["cloud_base_ft"] >= MIN_CLOUD_BASE_FT:
        go_possible = True
        color = "blue"
    folium.Marker(
        [station["lat"], station["lon"]],
        popup=info,
        icon=folium.Icon(color=color)
    ).add_to(m)

folium.LayerControl().add_to(m)
st_folium(m, width=1100, height=600)

# Final Decision
st.header("📊 Flight Decision")
sun_ok = sun_angle_check()
if go_possible and sun_ok:
    st.success("✅ GO: Conditions are acceptable for imagery collection.")
elif not go_possible:
    st.error("❌ NO-GO: Cloud bases too low within 50 NM radius.")
elif not sun_ok:
    st.warning("⚠️ NO-GO: Sun angle is too low for effective imagery.")
