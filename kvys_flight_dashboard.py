import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from geopy.distance import geodesic

# Constants
RADIUS_NM = 50
FT_BUFFER = 500
DEFAULT_COLLECTION_ALTITUDE = 8500  # ft MSL (8000 + 500 buffer)

# Known airports for selection
AIRPORTS = {
    "KVYS": (41.3517, -89.1530),  # Illinois Valley Regional
    "KPIA": (40.6642, -89.6933),
    "KBMI": (40.4771, -88.9156),
    "KRFD": (42.1954, -89.0972),
    "KMLI": (41.4486, -90.5075),
}

# Title
st.title("✈️ KVYS Flight Weather Dashboard")

# Select departure airport
icao = st.selectbox("Select Departure Airport (ICAO):", list(AIRPORTS.keys()))
lat, lon = AIRPORTS[icao]

# Select time window
start_hour = st.slider("Flight Start Hour (CST)", 8, 17, 10)
end_hour = st.slider("Flight End Hour (CST)", start_hour, 18, start_hour + 1)

# Fetch METARs via NOAA ADDS API
def fetch_metars(lat, lon):
    url = "https://aviationweather.gov/adds/dataserver_current/httpparam"
    params = {
        "dataSource": "metars",
        "requestType": "retrieve",
        "format": "xml",
        "radialDistance": f"{RADIUS_NM};{lon},{lat}",
        "hoursBeforeNow": 2
    }
    response = requests.get(url, params=params)
    root = ET.fromstring(response.content)

    stations = []

    for metar in root.iter("METAR"):
        station_id = metar.findtext("station_id", default="UNKNOWN")
        raw_text = metar.findtext("raw_text", default="")
        flight_category = metar.findtext("flight_category", default="UNK")
        latitude = float(metar.findtext("latitude", default="0"))
        longitude = float(metar.findtext("longitude", default="0"))
        elevation_m = float(metar.findtext("elevation_m", default="0"))
        cloud_base_ft_agl = None

        for sky in metar.findall("sky_condition"):
            if sky.attrib.get("sky_cover") in ["BKN", "OVC"]:
                cloud_base_ft_agl = float(sky.attrib.get("cloud_base_ft_agl", 0))
                break

        if cloud_base_ft_agl is not None:
            cloud_base_ft_msl = cloud_base_ft_agl + elevation_m * 3.281
        else:
            cloud_base_ft_msl = None

        stations.append({
            "station_id": station_id,
            "lat": latitude,
            "lon": longitude,
            "flight_category": flight_category,
            "cloud_base_ft_msl": cloud_base_ft_msl,
            "raw_text": raw_text
        })

    return pd.DataFrame(stations)

# Display METAR
metar_df = fetch_metars(lat, lon)

st.subheader(f"📡 Current METAR for {icao}")
selected = metar_df[metar_df["station_id"] == icao]
if not selected.empty:
    st.code(selected.iloc[0]["raw_text"])
else:
    st.warning("No METAR available for this airport.")

# Evaluate GO/NO-GO
go = all(
    row["cloud_base_ft_msl"] is not None and row["cloud_base_ft_msl"] >= DEFAULT_COLLECTION_ALTITUDE
    for _, row in metar_df.iterrows()
)

st.markdown(f"### 🚦 Flight Status: {'✅ GO' if go else '❌ NO-GO'}")
st.markdown(f"**Required Cloud Base:** ≥ {DEFAULT_COLLECTION_ALTITUDE} ft MSL")

# Map View
st.subheader("🗺️ METAR Stations Map")

map_center = (lat, lon)
m = folium.Map(location=map_center, zoom_start=8, tiles="Esri.WorldImagery")
marker_cluster = MarkerCluster().add_to(m)

for _, row in metar_df.iterrows():
    color = {
        "VFR": "green",
        "MVFR": "blue",
        "IFR": "red",
        "LIFR": "purple",
        "UNK": "gray"
    }.get(row["flight_category"], "gray")

    popup = f"""
    <b>{row['station_id']}</b><br>
    Category: {row['flight_category']}<br>
    Cloud Base (MSL): {row['cloud_base_ft_msl']:.0f if row['cloud_base_ft_msl'] else 'N/A'} ft<br>
    METAR: {row['raw_text']}
    """
    folium.CircleMarker(
        location=(row["lat"], row["lon"]),
        radius=6,
        color=color,
        fill=True,
        fill_opacity=0.7,
        popup=folium.Popup(popup, max_width=300)
    ).add_to(marker_cluster)

st_data = st_folium(m, width=800, height=600)
