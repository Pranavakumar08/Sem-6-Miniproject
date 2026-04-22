import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from tarapath_core.pipeline import run_tarapath, TarapathConfig
from tarapath_core.solver import estimate_location

app = FastAPI(title="Tarapath API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TMP_DIR = Path("tmp_uploads")
TMP_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/health")
def health():
    return {"status": "ok", "solver": "tetra3"}

@app.post("/estimate")
async def estimate(
    image: UploadFile = File(...),
    timestamp: Optional[str] = Form(None),
    tz_offset_hours: float = Form(0.0),
    last_lat: Optional[float] = Form(None),
    last_lon: Optional[float] = Form(None),
    camera_tilt_deg: float = Form(5.0)
):
    start_time = time.time()
    tmp_path = None
    try:
        # Save uploaded image
        tmp_path = TMP_DIR / f"{int(time.time())}_{image.filename}"
        with open(tmp_path, "wb") as f:
            f.write(await image.read())
        
        # Parse timestamp
        astro_time = None
        if timestamp:
            dt_naive = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            tz = timezone(timedelta(hours=tz_offset_hours))
            astro_time = dt_naive.replace(tzinfo=tz)
        
        # GPS prior
        last_gps = None
        if last_lat is not None and last_lon is not None:
            last_gps = (last_lat, last_lon)

        # Configure pipeline
        config = TarapathConfig(
            assumed_camera_tilt_deg=camera_tilt_deg
        )
        
        # Run pipeline (gets plate solution and cross-matched stars)
        pipeline_result = run_tarapath(
            image_path=str(tmp_path),
            timestamp_override=astro_time,
            config=config
        )

        if pipeline_result.error_message:
            return {
                "success": False,
                "error_message": pipeline_result.error_message
            }

        # Handle timestamp for solver if none was provided (extract from EXIF)
        from astropy.time import Time as AstropyTime
        if astro_time is None:
            from tarapath_core.exif_utils import read_exif_datetime
            exif_ts = read_exif_datetime(str(tmp_path))
            if exif_ts:
                obs_time = AstropyTime(exif_ts)
            else:
                return {"success": False, "error_message": "No timestamp provided and no EXIF data found."}
        else:
            obs_time = AstropyTime(astro_time)

        # Refine location using the 3-stage solver
        final_result = estimate_location(
            observed_stars=pipeline_result.used_stars,
            timestamp=obs_time,
            last_gps=last_gps
        )

        if final_result.error_message:
            return {
                "success": False,
                "error_message": final_result.error_message
            }
        
        solver_time_ms = int((time.time() - start_time) * 1000)
        stars_used = [s.name for s in final_result.used_stars]
        
        print(f"[API] Estimate: img={image.filename}, time={timestamp}, prior={last_gps}, time={solver_time_ms}ms")

        return {
            "success": True,
            "latitude": final_result.latitude,
            "longitude": final_result.longitude,
            "confidence": final_result.confidence,
            "error_radius_km": final_result.error_radius_km,
            "stars_used": stars_used,
            "solver_time_ms": solver_time_ms,
            "error_message": None
        }

    except Exception as e:
        return {"success": False, "error_message": str(e)}
    finally:
        # Cleanup
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
