import streamlit as st
import requests
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import folium
from streamlit_folium import st_folium

# --------------------------
# Config
# --------------------------
COLLECTION_ALTITUDE_FT = 8500
CLOUD_BUFFER_FT = 500
RADIUS_NM = 50
OPENWEATHER_API_KEY = "YOUR_OPENWEATHERMAP_API_KEY"  # Replace with your real key

# --------------------------
# Helper Functions
# --------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 3440.065  # NM
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return 2 * R * asin(sqrt(a))

def get_metars_from_api(center_lat, center_lon):
    url = f"https://aviationweather.gov/api/data/metar?bbox={center_lon-2},{center_lat-2},{center_lon+2},{center_lat+2}&format=json"
    res = requests.get(url)
    res.raise_for_status()
    return res.json()

def get_metar_by_icao(icao_id):
    url = f"https://aviationweather.gov/api/data/metar?ids={icao_id}&format=json"
    res = requests.get(url)
    res.raise_for_status()
    data = res.json()
    if data and "rawText" in data[0]:
        return data[0]["rawText"], data[0]["latitude"], data[0]["longitude"]
    return "METAR not available", None, None

def parse_metars(metars, center_lat, center_lon):
    stations = []
    for metar in metars:
        if not all(k in metar for k in ("latitude", "longitude", "rawText")):
            continue
        dist = haversine(center_lat, center_lon, metar["latitude"], metar["longitude"])
        if dist <= RADIUS_NM:
            station = {
                "icao": metar.get("icaoId", "UNK"),
                "lat": metar["latitude"],
                "lon": metar["longitude"],
                "flight_category": metar.get("flightCategory", "UNK"),
                "raw_text": metar["rawText"],
                "cloud_base_ft": None
            }
            clouds = metar.get("skyCondition", [])
            if isinstance(clouds, list):
                for layer in clouds:
                    if "cloudBaseFtAgl" in layer:
                        elevation_m = metar.get("elevationM", 0)
                        cloud_base_msl = layer["cloudBaseFtAgl"] + elevation_m * 3.28084
                        station["cloud_base_ft"] = round(cloud_base_msl)
                        break
            stations.append(station)
    return stations

def current_time_cst():
    return (datetime.utcnow() - timedelta(hours=5)).time()

def within_user_window(start_time_str, end_time_str):
    now = current_time_cst()
    start = datetime.strptime(start_time_str, "%H:%M").time()
    end = datetime.strptime(end_time_str, "%H:%M").time()
    return start <= now <= end

# --------------------------
# Streamlit App
# --------------------------
st.set_page_config(layout="wide")
st.title("📡 Aerial Imagery Go/No-Go Dashboard")

# ICAO selection
icao_input = st.text_input("Enter Launch Airport ICAO Code (e.g., KVYS):", "KVYS").upper()

# Time window selection
col1, col2 = st.columns(2)
with col1:
    start_time = st.time_input("Flight Window Start (CST)", value=datetime.strptime("08:00", "%H:%M").time())
with col2:
    end_time = st.time_input("Flight Window End (CST)", value=datetime.strptime("18:00", "%H:%M").time())

# Show METAR
with st.spinner(f"Getting METAR for {icao_input}..."):
    try:
        metar_text, center_lat, center_lon = get_metar_by_icao(icao_input)
        if not center_lat:
            st.error("Could not retrieve location from METAR.")
            st.stop()
        st.markdown(f"**Current METAR for {icao_input}:** `{metar_text}`")
    except Exception as e:
        st.error(f"Error retrieving METAR: {e}")
        st.stop()

# METAR analysis
with st.spinner("Fetching nearby METARs..."):
    try:
        raw_metars = get_metars_from_api(center_lat, center_lon)
        stations = parse_metars(raw_metars, center_lat, center_lon)
    except Exception as e:
        st.error(f"Error retrieving METARs: {e}")
        st.stop()

# Map setup
m = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles=None)
folium.TileLayer("Esri.WorldImagery").add_to(m)

folium.raster_layers.TileLayer(
    tiles=f"https://tile.openweathermap.org/map/clouds_new/{{z}}/{{x}}/{{y}}.png?appid={OPENWEATHER_API_KEY}",
    attr="OpenWeatherMap", name="Clouds", overlay=True, control=True, opacity=0.5
).add_to(m)

# Station markers
go_possible = False
for s in stations:
    cloud_ok = s["cloud_base_ft"] and s["cloud_base_ft"] >= COLLECTION_ALTITUDE_FT + CLOUD_BUFFER_FT
    color = "green" if s["flight_category"] == "VFR" else "red"
    if cloud_ok:
        color = "blue"
        go_possible = True
    popup = f"""
    <b>{s['icao']}</b><br>
    Category: {s['flight_category']}<br>
    Cloud Base: {s['cloud_base_ft']} ft<br>
    METAR: {s['raw_text']}
    """
    folium.Marker([s["lat"], s["lon"]], popup=popup, icon=folium.Icon(color=color)).add_to(m)

folium.LayerControl().add_to(m)
st_folium(m, width=1100, height=600)

# Decision logic
st.header("📊 Flight Decision")
if go_possible and within_user_window(start_time.strftime("%H:%M"), end_time.strftime("%H:%M")):
    st.success("✅ GO: Conditions are acceptable for imagery collection.")
elif not go_possible:
    st.error("❌ NO-GO: Cloud bases too low at one or more reporting stations.")
else:
    st.warning("⚠️ NO-GO: Outside your selected flight window.")
