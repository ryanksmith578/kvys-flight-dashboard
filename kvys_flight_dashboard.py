import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from astral.sun import sun
from astral import LocationInfo
import folium
from streamlit_folium import st_folium

# Constants
kvys_lat = 41.3514
kvys_lon = -89.1531
collection_alt_ft = 8500
min_cloud_base_ft_agl = collection_alt_ft + 500  # Require 500' buffer
map_radius_nm = 50

# App title
st.title("KVYS Flight Weather Dashboard")
st.write("Visual weather decision tool for imagery collection flights at 8500' MSL.")

# Convert nautical miles to degrees (approx for lat/lon)
nm_to_deg = lambda nm: nm / 60.0

# Get local date (CST)
now_cst = datetime.now(ZoneInfo("America/Chicago"))

# ☀️ Sun elevation window
def get_sun_window(lat, lon, date):
    city = LocationInfo(name="KVYS", region="USA", timezone="America/Chicago", latitude=lat, longitude=lon)
    s = sun(city.observer, date=date, tzinfo=ZoneInfo("America/Chicago"))
    return s['dawn'], s['dusk']

sun_start, sun_end = get_sun_window(kvys_lat, kvys_lon, now_cst.date())
st.markdown(f"☀️ **Sun Elevation Window (≥30°)**: {sun_start.strftime('%I:%M %p')} – {sun_end.strftime('%I:%M %p')} CST")

# METAR API (AviationWeather.gov)
def get_metars(lat, lon, radius_nm=50):
    endpoint = "https://aviationweather.gov/api/data/metar"
    params = {
        "bbox": f"{lon - nm_to_deg(radius_nm)},{lat - nm_to_deg(radius_nm)},"
                f"{lon + nm_to_deg(radius_nm)},{lat + nm_to_deg(radius_nm)}",
        "format": "json"
    }
    try:
        res = requests.get(endpoint, params=params)
        return res.json()
    except Exception as e:
        st.error(f"Failed to fetch METARs: {e}")
        return []

metars = get_metars(kvys_lat, kvys_lon)

# 🛩️ Flight decision logic
go_status = "NO-GO"
reasons = []

# Parse cloud base from METARs
def extract_cloud_base(metar):
    if "sky_condition" in metar:
        for condition in metar["sky_condition"]:
            if condition.get("sky_cover") in ("BKN", "OVC"):
                base_hundreds_ft = int(condition.get("cloud_base_ft_agl", 0))
                return base_hundreds_ft * 100
    return None

valid_bases = []

for metar in metars:
    cloud_base = extract_cloud_base(metar)
    if cloud_base and cloud_base >= min_cloud_base_ft_agl:
        valid_bases.append(cloud_base)

if valid_bases:
    go_status = "GO"
else:
    reasons.append(f"No stations reporting cloud base ≥ {min_cloud_base_ft_agl} ft AGL")

st.subheader(f"🚦 Flight Decision: **{go_status}**")
if reasons:
    st.write("Reasons:")
    for r in reasons:
        st.write(f"- {r}")

# 📍 Map with METAR overlay
st.subheader("🗺️ Cloud Base Map Overlay")

m = folium.Map(location=[kvys_lat, kvys_lon], zoom_start=8, tiles=None)

# Use Google Satellite + optional cloud overlay (from OpenWeatherMap)
folium.TileLayer(
    tiles='http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
    attr='Google Satellite',
    name='Satellite',
    subdomains=['mt0', 'mt1', 'mt2', 'mt3'],
    max_zoom=20
).add_to(m)

# Add cloud overlay tile layer
folium.TileLayer(
    tiles="https://tile.openweathermap.org/map/clouds_new/{z}/{x}/{y}.png?appid=YOUR_API_KEY",
    attr="Clouds © OpenWeatherMap",
    name="Clouds",
    overlay=True,
    control=True,
    opacity=0.5
).add_to(m)

# Add METAR points
for metar in metars:
    station = metar.get("station_id", "")
    lat = metar.get("latitude")
    lon = metar.get("longitude")
    base = extract_cloud_base(metar)

    if lat and lon:
        color = "green" if base and base >= min_cloud_base_ft_agl else "red"
        label = f"{station}<br>Cloud Base: {base or 'N/A'} ft AGL"
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            popup=label,
            color=color,
            fill=True,
            fill_opacity=0.7
        ).add_to(m)

# Add radius circle
folium.Circle(
    location=[kvys_lat, kvys_lon],
    radius=map_radius_nm * 1852,  # convert NM to meters
    color="blue",
    fill=False
).add_to(m)

folium.LayerControl().add_to(m)
st_folium(m, width=725)

# Footer
st.caption("KVYS Flight Weather Tool – Built with ❤️ using Streamlit & Folium")
