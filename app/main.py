import os
from datetime import datetime
from pathlib import Path

import streamlit as st
import folium
from streamlit.components.v1 import html
from dotenv import load_dotenv

from tarapath_core.pipeline import run_tarapath, TarapathConfig
from tarapath_core.exif_utils import read_exif_datetime

# Load .env so ASTROMETRY_API_KEY is available even without setting it in the shell
load_dotenv()


st.set_page_config(page_title="Tarapath – Celestial Navigation", layout="wide")

st.title("Tarapath – Sky Photo Based Ship Position Estimator")
st.write(
    "Estimate your ship's location from a night-sky photograph, without relying on GPS. "
    "Upload a clear sky photo with stars visible and a valid capture timestamp."
)


def render_map(lat: float, lon: float, radius_km: float) -> None:
    m = folium.Map(location=[lat, lon], zoom_start=4)
    folium.Marker([lat, lon], tooltip="Estimated position").add_to(m)
    folium.Circle(
        radius=radius_km * 1000.0,
        location=[lat, lon],
        color="blue",
        fill=True,
        fill_opacity=0.1,
    ).add_to(m)
    map_html = m._repr_html_()
    html(map_html, height=500)


uploaded_file = st.file_uploader("Upload a night-sky image", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded sky image", use_container_width=True)

    # Save to a temp path so we can read EXIF immediately
    tmp_dir = Path("tmp_uploads")
    tmp_dir.mkdir(exist_ok=True)
    img_path = tmp_dir / uploaded_file.name
    with open(img_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # --- Timestamp detection ---
    exif_ts = read_exif_datetime(str(img_path))

    if exif_ts is not None:
        st.success(
            f"✅ EXIF timestamp detected: **{exif_ts.strftime('%Y-%m-%d %H:%M:%S')} UTC**  "
            "You can override it below if needed."
        )
        default_ts_str = exif_ts.strftime("%Y-%m-%d %H:%M:%S")
    else:
        st.warning(
            "⚠️ No EXIF timestamp found in this image.  "
            "Please enter the photo capture time (UTC) below before estimating."
        )
        default_ts_str = ""

    timestamp_override_str = st.text_input(
        "Capture timestamp (UTC) — format: YYYY-MM-DD HH:MM:SS",
        value=default_ts_str,
        placeholder="e.g. 2024-06-15 21:30:00",
    )

    # --- Advanced settings ---
    with st.expander("Advanced settings"):
        lat_min = st.number_input("Latitude min", value=-90.0)
        lat_max = st.number_input("Latitude max", value=90.0)
        lon_min = st.number_input("Longitude min", value=-180.0)
        lon_max = st.number_input("Longitude max", value=180.0)
        match_tol = st.number_input("Star match tolerance (degrees)", value=1.0)

    # --- Validate timestamp before allowing estimation ---
    ts_override: datetime | None = None
    ts_valid = False

    if timestamp_override_str.strip():
        try:
            ts_override = datetime.strptime(timestamp_override_str.strip(), "%Y-%m-%d %H:%M:%S")
            ts_valid = True
        except ValueError:
            st.error("❌ Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS (e.g. 2024-06-15 21:30:00).")
    else:
        # No EXIF and no override → show a hint and disable the button
        if exif_ts is None:
            st.info("ℹ️ Enter a capture timestamp above to enable position estimation.")

    # If EXIF was found and user hasn't typed anything, ts_override is effectively the EXIF time
    # (pipeline will use it automatically if ts_override is None, so only block when NEITHER exists)
    can_estimate = ts_valid or (exif_ts is not None and not timestamp_override_str.strip())

    api_key = os.getenv("ASTROMETRY_API_KEY")
    if not api_key:
        st.warning(
            "⚠️ `ASTROMETRY_API_KEY` environment variable is not set. "
            "Plate solving will fail. Set it with:\n"
            "```powershell\n$env:ASTROMETRY_API_KEY = 'your_key_here'\n```"
        )

    cfg = TarapathConfig(
        catalog_path="data/star_catalog/hyg_stars.csv",
        astrometry_api_key=api_key,
        match_tolerance_deg=match_tol,
        lat_bounds=(lat_min, lat_max),
        lon_bounds=(lon_min, lon_max),
    )

    if st.button("Estimate position", disabled=not can_estimate):
        with st.spinner("Solving plate and estimating position… this can take a few minutes."):
            result = run_tarapath(str(img_path), timestamp_override=ts_override, config=cfg)

        if result.error_message:
            st.error(f"❌ {result.error_message}")
        else:
            st.subheader("Estimated Position")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Latitude", f"{result.latitude:.4f}°")
            col2.metric("Longitude", f"{result.longitude:.4f}°")
            col3.metric("Confidence", f"{result.confidence * 100:.1f}%")
            col4.metric("Error radius", f"{result.error_radius_km:.1f} km")

            if result.used_stars:
                st.subheader("Stars used in fix")
                names = ", ".join(sorted({s.name for s in result.used_stars}))
                st.write(names)

            st.subheader("Map")
            render_map(result.latitude, result.longitude, result.error_radius_km)
