import streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun

st.set_page_config(page_title="📡 KVYS Flight Weather Dashboard", layout="centered")

station = "KVYS"
radius_nm = 50
collection_alt_ft = 8000
min_cloud_base_ft = collection_alt_ft + 500
aviation_api = "https://aviationweather.gov/adds/dataserver_current/httpparam"

st.title("📡 KVYS Flight Weather Dashboard")
st.markdown("Analyze if conditions support aerial image collection at **7,500 ft MSL** within a 50 nm radius of KVYS.")

params_metar = {
    "dataSource": "metars", "requestType": "retrieve", "format": "xml",
    "stationString": station, "hoursBeforeNow": 2, "radialDistance": f"{radius_nm};{station}"
}
params_taf = {
    "dataSource": "tafs", "requestType": "retrieve", "format": "xml",
    "stationString": station, "hoursBeforeNow": 0, "radialDistance": f"{radius_nm};{station}"
}

def fetch_data():
    m = requests.get(aviation_api, params=params_metar)
    t = requests.get(aviation_api, params=params_taf)
    return ET.fromstring(m.content), ET.fromstring(t.content)

def parse_metar(root):
    return [int(sky.attrib["cloud_base_ft_agl"])
            for metar in root.findall(".//METAR")
            for sky in metar.findall("sky_condition")
            if "cloud_base_ft_agl" in sky.attrib]

def parse_taf(root):
    return [taf.findtext("raw_text") for taf in root.findall(".//TAF")]

def get_sun_window(lat, lon, date):
    city = LocationInfo("KVYS", "CA", "US/Central", lat, lon)
    s = sun(city.observer, date=date)
    return s["sunrise"] + timedelta(hours=1.5), s["sunset"] - timedelta(hours=1.5)

with st.spinner("Fetching weather data…"):
    try:
        metar_root, taf_root = fetch_data()
        cloud_bases = parse_metar(metar_root)
        min_base = min(cloud_bases) if cloud_bases else 99999
        tafs = parse_taf(taf_root)
        sun_start, sun_end = get_sun_window(41.35, -89.15, datetime.utcnow().date())
        decision = "✅ GO" if min_base > min_cloud_base_ft else "❌ NO‑GO"

        st.subheader("📡 METAR Summary")
        st.write(f"Lowest observed cloud base: **{min_base} ft AGL**")
        st.write(f"Required minimum cloud base: **{min_cloud_base_ft} ft AGL**")

        st.subheader("🌤️ Sun Elevation Window (≥30°)")
        st.write(f"Local time: **{sun_start.time()} – {sun_end.time()}**")

        st.subheader("📝 TAF Forecast (Next 24 hrs)")
        st.code(tafs[0] if tafs else "No TAF available")

        st.subheader("🚦 Flight Decision")
        st.markdown(f"# {decision}")
    except Exception as e:
        st.error(f"Error: {e}")
