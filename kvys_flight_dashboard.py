import streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun

# --- CONFIGURATION ---
st.set_page_config(page_title="📡 KVYS Flight Weather Dashboard", layout="centered")
station = "KVYS"
radius_nm = 50
collection_alt_ft = 8500  # NEW collection altitude
field_elevation_ft = 650
required_base_msl = collection_alt_ft + 500  # MSL base must be at least 500' higher
min_cloud_base_ft = required_base_msl - field_elevation_ft  # AGL minimum: 9000 - 650 = 8350

aviation_api = "https://aviationweather.gov/adds/dataserver_current/httpparam"
params_metar = {
    "dataSource": "metars", "requestType": "retrieve", "format": "xml",
    "stationString": station, "hoursBeforeNow": 2, "radialDistance": f"{radius_nm};{station}"
}
params_taf = {
    "dataSource": "tafs", "request
