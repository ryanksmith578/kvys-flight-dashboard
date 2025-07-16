import streamlit as st
import requests
from datetime import datetime, timedelta
import pytz
import math
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic

# --- Settings ---
collection_alt_ft = 8500
min_cloud_base_ft = collection_alt_ft + 500
radius_nm = 50

# --- ICAO airport locations (you can expand this dictionary) ---
airport_coords = {
    "KVYS": (41.351, -89.153),  # Peru, IL
    "KPIA": (40.6642, -89.6933),
    "KBMI": (40.4771, -88.9156),
    "KRFD": (42.1954, -89.0972),
    "KORD": (41.9786, -87.9048),
}

# --- Streamlit UI ---
st.set_page_config(page_title="Flight Weather Dashboard", layout="wide")
st.title("📡 Flight Weather Dashboard for Imagery Collection")

# --- User Inputs ---
icao = st.selectbox("Select launch airport (ICAO)", list(airport_coords.keys()), index=0)
start_hour = st.slider("Flight start time (CST)", 6, 17, 8)
end_hour = st.slider("Flight end time (CST)", start_hour + 1, 18, 10)

launch_coords = airport_coords[icao]

# --- Time setup ---
cst = pytz.timezone("US/Central")
now = datetime.now(cst)
today_start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
today_end = now.replace(hour=end_hour, minute=0, second=0, microsecond=0)

# --- NOAA ADDS API (METAR XML) ---
def get_metar_data():
    url = (
        f"https://aviationweather.gov/adds/dataserver_current/httpparam?"
        f"dataSource=metars&requestType=retrieve&format=xml&stationString=~"
        f"&radialDistance={radius_nm};{launch_coords[1]},{launch_coords[0]}"
        f"&hoursBeforeNow=2"
    )
    r = requests.get(url)
    return r.text

# --- Parse METAR XML ---
from xml.etree import ElementTree as ET

def parse_metars(xml_data):
    root = ET.fromstring(xml_data)
    stations = []
    for metar in root.findall(".//METAR"):
        station_id = metar.findtext("station_id")
        flight_cat = metar.findtext("flight_category", "UNK")
        raw_text = metar.findtext("raw_text", "")
        lat = float(metar.findtext("latitude", 0))
        lon = float(metar.findtext("longitude", 0))

        cloud_base = None
        for sky in metar.findall("sky_condition"):
            sky_cover = sky.attrib.get("sky_cover", "")
            if "BKN" in sky_cover or "OVC" in sky_cover:
                base_ft = int(sky.attrib.get("cloud_base_ft_agl", "0"))
                cloud_base = base_ft
                break

        stations.append({
            "station_id": station_id,
            "flight_category": flight_cat,
            "raw_text": raw_text,
            "lat": lat,
            "lon": lon,
            "cloud_base": cloud_base
        })
    return stations

# --- Main Weather Processing ---
xml_data = get_metar_data()
stations = parse_metars(xml_data)

# --- Show METAR for selected airport ---
launch_metar = next((s for s in stations if s["station_id"] == icao), None)
if launch_metar:
    st.subheader(f"Current METAR for {icao}")
    st.code(launch_metar["raw_text"])
else:
    st.warning(f"No recent METAR found for {icao}")

# --- Go/No-Go Decision ---
valid_stations = []
for s in stations:
    if s["cloud_base"] and (s["cloud_base"] >= min_cloud_base_ft):
        valid_stations.append(s)

decision = "✅ GO" if all(s["cloud_base"] and s["cloud_base"] >= min_cloud_base_ft for s in valid_stations) else "❌ NO-GO"
st.subheader("Flight Decision")
st.markdown(f"**Collection Altitude:** {collection_alt_ft} ft MSL")
st.markdown(f"**Minimum Cloud Base Required:** {min_cloud_base_ft} ft MSL")
st.markdown(f"**Flight Time Window:** {start_hour}:00–{end_hour}:00 CST")
st.markdown(f"**Go/No-Go Decision:** {decision}")

# --- Map Display ---
st.subheader("Flight Category Map (within 50 NM)")
m = folium.Map(location=launch_coords, zoom_start=8, tiles="Esri.WorldImagery")

color_map = {
    "VFR": "green",
    "MVFR": "blue",
    "IFR": "red",
    "LIFR": "purple"
}

for s in stations:
    color = color_map.get(s["flight_category"], "gray")
    popup = f"{s['station_id']}<br>{s['flight_category']}<br>{s['raw_text']}"
    folium.CircleMarker(
        location=(s["lat"], s["lon"]),
        radius=6,
        color=color,
        fill=True,
        fill_opacity=0.7,
        popup=popup
    ).add_to(m)

folium.Circle(
    radius=radius_nm * 1852,
    location=launch_coords,
    color='yellow',
    fill=False
).add_to(m)

st_folium(m, width=1000, height=600)
