import os
from datetime import datetime
from pathlib import Path

import streamlit as st
import folium
from streamlit.components.v1 import html
from dotenv import load_dotenv

from tarapath_core.pipeline import run_tarapath, TarapathConfig
from tarapath_core.exif_utils import read_exif_datetime
from tarapath_core.retry_solver import solve_with_retries

load_dotenv()

st.set_page_config(page_title="Tarapath – Celestial Navigation", layout="wide")
st.title("Tarapath – Sky Photo Based Ship Position Estimator")
st.write(
    "Estimate your ship's location from a night-sky photograph, without relying on GPS. "
    "Upload a clear sky photo with stars visible and a valid capture timestamp."
)
st.info(
    "💡 **Accuracy Note:** This tool calculates location assuming the camera is pointing straight up at "
    "the Zenith. Any tilt in the camera translates directly to position error "
    "(1° of tilt = ~111 km of error). For accurate results, lay the phone flat on a level surface."
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

    tmp_dir = Path("tmp_uploads")
    tmp_dir.mkdir(exist_ok=True)
    img_path = tmp_dir / uploaded_file.name
    with open(img_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    exif_ts = read_exif_datetime(str(img_path))
    default_tz_offset = 0.0

    if exif_ts is not None:
        if exif_ts.tzinfo is not None:
            st.success(
                f"✅ EXIF timestamp & timezone detected: **{exif_ts.strftime('%Y-%m-%d %H:%M:%S')} UTC**  "
                "You can override it below if needed."
            )
            default_ts_str = exif_ts.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
        else:
            st.warning(
                f"⚠️ EXIF timestamp found (**{exif_ts.strftime('%Y-%m-%d %H:%M:%S')}**) but **no timezone**.  "
                "Please specify your local timezone offset below so it can be converted to UTC."
            )
            default_ts_str = exif_ts.strftime("%Y-%m-%d %H:%M:%S")
    else:
        st.warning(
            "⚠️ No EXIF timestamp found in this image.  "
            "Please enter the photo capture time (UTC) below before estimating."
        )
        default_ts_str = ""

    timestamp_override_str = st.text_input(
        "Capture timestamp (Local Time or UTC) – format: YYYY-MM-DD HH:MM:SS",
        value=default_ts_str,
        placeholder="e.g. 2024-06-15 21:30:00",
    )

    tz_offset_hours = st.number_input(
        "Timezone Offset (hours from UTC)",
        value=default_tz_offset,
        step=0.5,
        help="If the photo was taken in India (IST), enter 5.5. If in New York (EST), enter -5.0."
    )

    st.markdown("### Camera Leveling & Accuracy")
    camera_tilt = st.slider(
        "Estimated Camera Tilt Error (degrees)",
        min_value=0, max_value=45, value=5, step=1,
    )

    with st.expander("Advanced settings"):
        match_tol = st.number_input("Star match tolerance (degrees)", value=1.0)

    from datetime import timezone, timedelta
    ts_override: datetime | None = None
    ts_valid = False

    if timestamp_override_str.strip():
        try:
            naive_dt = datetime.strptime(timestamp_override_str.strip(), "%Y-%m-%d %H:%M:%S")
            tz = timezone(timedelta(hours=tz_offset_hours))
            local_dt = naive_dt.replace(tzinfo=tz)
            ts_override = local_dt.astimezone(timezone.utc)
            ts_valid = True
        except ValueError:
            st.error("❌ Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS.")
    else:
        if exif_ts is None:
            st.info("ℹ️ Enter a capture timestamp above to enable position estimation.")

    can_estimate = ts_valid or (
        exif_ts is not None and
        getattr(exif_ts, 'tzinfo', None) is not None and
        not timestamp_override_str.strip()
    )

    # Removed Astrometry API key warning as we use offline tetra3.
    # We still fetch it just in case config expects it (it defaults to None in TarapathConfig anyway).
    api_key = os.getenv("ASTROMETRY_API_KEY")

    cfg = TarapathConfig(
        catalog_path="data/star_catalog/hyg_stars.csv",
        astrometry_api_key=api_key,
        match_tolerance_deg=match_tol,
        assumed_camera_tilt_deg=float(camera_tilt),
    )

    if st.button("Estimate position", disabled=not can_estimate):
        with st.status("Estimating position...", expanded=True) as status:
            
            def progress(msg: str):
                status.write(msg)
                
            result = solve_with_retries(
                image_path=img_path,
                timestamp_override=ts_override,
                config=cfg,
                tz_offset_hours=tz_offset_hours,
                progress_callback=progress,
            )

            if result.error_message and result.diagnostics.get("fallback"):
                status.update(
                    label="⚠️ Star solving failed — showing timezone estimate",
                    state="complete",
                    expanded=False
                )
            elif result.error_message:
                status.update(label="❌ Estimation failed", state="error", expanded=True)
            else:
                status.update(label="✅ Position estimated successfully!", state="complete", expanded=False)

        if result.error_message and not result.diagnostics.get("fallback"):
            st.error(f"❌ {result.error_message}")
        else:
            if result.diagnostics.get("fallback"):
                st.warning(
                    "⚠️ Could not solve star field after 5 attempts. "
                    "Showing approximate position based on timezone offset only. "
                    "Accuracy: ±5000 km. Upload a clearer night sky photo for GPS-level accuracy."
                )
                
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
