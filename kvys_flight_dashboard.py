import streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2

# --- CONFIGURATION ---
st.set_page_config(page_title="📡 KVYS Flight Weather Dashboard", layout="centered")

# Constants
station = "KVYS"
radius_nm = 50
collection_alt_ft = 8500
field_elevation_ft = 650
required_base_msl = collection_alt_ft + 500
min_cloud_base_ft = required_base_msl - field_elevation_ft  # = 8350 AGL

kvys_lat, kvys_lon = 41.35, -89.15

aviation_api = "https://aviationweather.gov/adds/dataserver_current/httpparam"

params_metar = {
    "dataSource": "metars"
