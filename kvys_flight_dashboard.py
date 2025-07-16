import streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2

# Configuration
st.set_page_config(page_title="📡 KVYS Flight Weather Dashboard", layout="centered")

# Constants
station = "KVYS"
radius_nm = 50
collection_alt_ft = 8500
field_elevation_ft = 650
required_base_msl = collection_alt_ft + 500
min_cloud_base_ft = required_base_msl - field_elevation_ft  # = 8350 ft AGL

kvys_lat, kvys_lon = 41.35, -89.15
aviation_api = "https://aviationweather.gov/adds/dataserver_current/httpparam"

params_metar = {
    "dataSource": "metars",
    "requestType": "retrieve",
    "format": "xml",
    "stationString": station,
    "hoursBeforeNow": 2,
    "radialDistance": f"{radius_nm};{station}"
}

params_taf = {
    "dataSource": "tafs",
    "requestType": "retrieve",
    "format": "xml",
    "stationString": station,
    "hoursBeforeNow": 0,
    "radialDistance": f"{radius_nm};{station}"
}

def fetch_data():
    metar_res = requests.get(aviation_api, params=params_metar)
    taf_res = requests.get(aviation_api, params=params_taf)
    return ET.fromstring(metar_res.content), ET.fromstring(taf_res.content)

def parse_metar(root):
    cloud_bases = []
    stations = []
    for metar in root.findall(".//METAR"):
        station_id = metar.findtext("station_id")
        lat = metar.findtext("latitude")
        lon = metar.findtext("longitude")
        base = None
        for sky in metar.findall("sky_condition"):
            if "cloud_base_ft_agl" in sky.attrib:
                base = int(sky.attrib["cloud_base_ft_agl"])
                break
        if base:
            cloud_bases.append(base)
            if station_id and lat and lon:
                stations.append({
                    "id": station_id,
                    "lat": float(lat),
                    "lon": float(lon),
                    "base": base,
                    "go": base > min_cloud_base_ft
                })
    return cloud_bases, stations

def parse_taf(root):
    return [taf.findtext("raw_text") for taf in root.findall(".//TAF")]

def get_sun_window(lat, lon, date):
    city = LocationInfo("KVYS", "IL", "US/Central", lat, lon)
    s = sun(city.observer, date=date)
    return s["sunrise"] + timedelta(hours=1.5), s["sunset"] - timedelta(hours=1.5)

def distance_nm(lat1, lon1, lat2, lon2):
    R = 3440  # nautical miles
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

# --- Streamlit App ---
with st.spinner("Fetching weather data…"):
    try:
        metar_root, taf_root = fetch_data()
        cloud_bases, stations = parse_metar(metar_root)
        min_base = min(cloud_bases) if cloud_bases else None
        tafs = parse_taf(taf_root)
        sun_start, sun_end = get_sun_window(kvys_lat, kvys_lon, datetime.utcnow().date())

        decision = "❌ NO‑GO"
        if min_base and min_base > min_cloud_base_ft:
            decision = "✅ GO"

        st.title("📡 KVYS Flight Weather Dashboard")

        st.subheader("🛫 Flight Parameters")
        st.write(f"- Collection Altitude (MSL): **{collection_alt_ft} ft**")
        st.write(f"- Required Cloud Base (MSL): **{required_base_msl} ft**")
        st.write(f"- Required Cloud Base (AGL): **{min_cloud_base_ft} ft**")

        st.subheader("📡 METAR Summary")
        if min_base:
            st.write(f"🔽 Lowest Observed Cloud Base: **{min_base} ft AGL**")
        else:
            st.warning("No cloud base data available.")

        st.subheader("📝 TAF Forecast (Next 24 hrs)")
        st.code(tafs[0] if tafs else "No TAF available")

        st.subheader("🌤️ Sun Elevation Window (≥30°)")
        st.write(f"Local time: **{sun_start.time()} – {sun_end.time()}**")

        st.subheader("🚦 Flight Decision")
        st.markdown(f"# {decision}")

        st.subheader("🗺️ Cloud Base Map (50 NM Radius)")
        fmap = folium.Map(location=[kvys_lat, kvys_lon], zoom_start=8)
        folium.Circle(
            location=[kvys_lat, kvys_lon],
            radius=radius_nm * 1852,
            color="blue", fill=False, dash_array="5,10"
        ).add_to(fmap)

        for s in stations:
            dist = distance_nm(kvys_lat, kvys_lon, s["lat"], s["lon"])
            if dist <= radius_nm:
                color = "green" if s["go"] else "red"
                folium.CircleMarker(
                    location=[s["lat"], s["lon"]],
                    radius=7,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.8,
                    popup=f"{s['id']}: {s['base']} ft AGL"
                ).add_to(fmap)

        st_data = st_folium(fmap, width=700, height=500)

    except Exception as e:
        st.error(f"❌ Error: {e}")
