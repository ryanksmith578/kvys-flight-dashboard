import streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic

# --- Settings ---
COLLECTION_ALT_FT = 8500
MIN_CLOUD_BASE_FT = COLLECTION_ALT_FT + 500
RADIUS_NM = 50

# Supported airports
AIRPORTS = {
    "KVYS": ("Illinois Valley Regional", 41.351, -89.153),
    "KBMI": ("Central Illinois Regional", 40.477, -88.915),
    "KPIA": ("Peoria International", 40.664, -89.693),
    "KRFD": ("Chicago Rockford", 42.195, -89.097),
}

st.set_page_config(page_title="Flight Weather Dashboard", layout="wide")
st.title("📡 Flight Weather Dashboard for Aerial Imagery")

# --- User Inputs ---
icao = st.selectbox("Launch Airport (ICAO)", list(AIRPORTS.keys()), index=0)
start_hour = st.slider("Start Time (CST)", 6, 17, 8)
end_hour = st.slider("End Time (CST)", start_hour + 1, 18, 16)

airport_name, lat0, lon0 = AIRPORTS[icao]
st.markdown(f"**Selected Airport**: {icao} — {airport_name} ({lat0}, {lon0})")
st.markdown(f"**Flight Window**: {start_hour:02d}:00–{end_hour:02d}:00 CST")

# --- Fetch METARs via NOAA ADDS API ---
def fetch_metars(lat, lon):
    url = (
        "https://aviationweather.gov/adds/dataserver_current/httpparam"
        "?dataSource=metars&requestType=retrieve&format=xml"
        f"&radialDistance={RADIUS_NM};{lon},{lat}"
        "&hoursBeforeNow=2"
    )
    r = requests.get(url)
    if r.status_code != 200:
        st.error("Error fetching METAR data.")
        return []
    root = ET.fromstring(r.text)
    return root.findall(".//METAR")

def parse_metar(elem):
    station = elem.findtext("station_id")
    raw = elem.findtext("raw_text", "")
    lat = float(elem.findtext("latitude", "0"))
    lon = float(elem.findtext("longitude", "0"))
    cat = elem.findtext("flight_category", "UNK")
    elev_m = float(elem.findtext("elevation_m", "0"))
    base_elem = elem.find("sky_condition")
    base_agl = int(base_elem.attrib.get("cloud_base_ft_agl", "0")) if base_elem is not None else 0
    base_msl = base_agl + elev_m * 3.28084
    return {"icao": station, "raw": raw, "lat": lat, "lon": lon, "cat": cat, "base_msl": base_msl}

elements = fetch_metars(lat0, lon0)
stations = [parse_metar(m) for m in elements]

# --- Display Launch Airport METAR ---
launch_metar = next((s for s in stations if s["icao"] == icao), None)
if launch_metar:
    st.subheader(f"Current METAR for {icao}")
    st.code(launch_metar["raw"])
else:
    st.warning(f"No METAR found for {icao}")

# --- Evaluate Go/No-Go ---
go = True
for s in stations:
    if s["base_msl"] < MIN_CLOUD_BASE_FT:
        go = False

st.subheader("🚦 Go / No‑Go Decision")
if go:
    st.success("✅ GO: All cloud bases are ≥ required threshold")
else:
    st.error("❌ NO‑GO: Some stations are below the required cloud base")

# --- Map of Stations ---
st.subheader("🗺️ Stations (within 50 NM) with Flight Category")
m = folium.Map(location=(lat0, lon0), zoom_start=7, tiles="Esri.WorldImagery")

color_by_cat = {"VFR":"green","MVFR":"blue","IFR":"red","LIFR":"purple","UNK":"gray"}
for s in stations:
    folium.CircleMarker(
        location=(s["lat"], s["lon"]),
        radius=6,
        color=color_by_cat.get(s["cat"], "gray"),
        fill=True, fill_opacity=0.7,
        popup=f"{s['icao']} | {s['cat']} | Base {int(s['base_msl'])} ft"
    ).add_to(m)

folium.Circle(location=(lat0, lon0), radius=RADIUS_NM*1852, color="yellow", fill=False).add_to(m)
st_folium(m, width=1000, height=600)
