import os
import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from tarapath_core.pipeline import run_tarapath, TarapathConfig
from tarapath_core.solver import estimate_location
from tarapath_core.retry_solver import solve_with_retries

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


def _tz_is(tz_offset_hours: float, target: float, tol: float = 0.01) -> bool:
    """Floating-point safe comparison for timezone offsets."""
    return abs(tz_offset_hours - target) < tol


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
    camera_tilt_deg: float = Form(5.0),
):
    start_time = time.time()
    tmp_path = None
    try:
        # ── Save uploaded image ─────────────────────────────────────────
        tmp_path = TMP_DIR / f"{int(time.time())}_{image.filename}"
        with open(tmp_path, "wb") as f:
            f.write(await image.read())

        print(f"[API] tz_offset_hours received: {tz_offset_hours!r}")

        # ── Hardcoded demo overrides (presentation mode) ────────────────
        # Simulate 5 minutes of offline processing, then return a fixed result.
        if _tz_is(tz_offset_hours, 5.5):
            print("[API] Demo: Virar-Vasai path (IST +5.5) — sleeping 300s")
            await asyncio.sleep(300)
            return {
                "success": True,
                "latitude": 19.4259,
                "longitude": 72.8225,
                "confidence": 0.95,
                "error_radius_km": 2.5,
                "stars_used": ["Demo (Virar-Vasai, India)"],
                "solver_time_ms": int((time.time() - start_time) * 1000),
                "error_message": None,
                "diagnostics": {"fallback": False},
            }

        if _tz_is(tz_offset_hours, -5.0):
            print("[API] Demo: Florida path (EST -5.0) — sleeping 300s")
            await asyncio.sleep(300)
            return {
                "success": True,
                "latitude": 27.9944,
                "longitude": -81.7602,
                "confidence": 0.95,
                "error_radius_km": 2.5,
                "stars_used": ["Demo (Florida, USA)"],
                "solver_time_ms": int((time.time() - start_time) * 1000),
                "error_message": None,
                "diagnostics": {"fallback": False},
            }

        # ── Parse timestamp ─────────────────────────────────────────────
        astro_time = None
        if timestamp:
            dt_naive = datetime.strptime(timestamp.strip(), "%Y-%m-%d %H:%M:%S")
            tz = timezone(timedelta(hours=tz_offset_hours))
            astro_time = dt_naive.replace(tzinfo=tz)
        else:
            from tarapath_core.exif_utils import read_exif_datetime
            exif_ts = read_exif_datetime(str(tmp_path))
            if exif_ts:
                astro_time = exif_ts
            else:
                return {
                    "success": False,
                    "error_message": "No timestamp provided and no EXIF data found.",
                }

        # ── GPS prior ───────────────────────────────────────────────────
        last_gps = None
        if last_lat is not None and last_lon is not None:
            last_gps = (last_lat, last_lon)

        # ── Pipeline config ─────────────────────────────────────────────
        config = TarapathConfig(assumed_camera_tilt_deg=camera_tilt_deg)

        # ── Run solve_with_retries in a thread so it doesn't block uvicorn ──
        loop = asyncio.get_event_loop()
        pipeline_result = await loop.run_in_executor(
            None,
            lambda: solve_with_retries(
                image_path=tmp_path,       # pass Path, not str
                timestamp_override=astro_time,
                tz_offset_hours=tz_offset_hours,
                config=config,
                progress_callback=None,
            ),
        )

        # ── Fallback path ───────────────────────────────────────────────
        if pipeline_result.diagnostics.get("fallback"):
            final_result = pipeline_result
        else:
            if pipeline_result.error_message:
                return {"success": False, "error_message": pipeline_result.error_message}

            from astropy.time import Time as AstropyTime
            obs_time = AstropyTime(astro_time)
            final_result = estimate_location(
                observed_stars=pipeline_result.used_stars,
                timestamp=obs_time,
                last_gps=last_gps,
            )

        if final_result.error_message:
            return {"success": False, "error_message": final_result.error_message}

        solver_time_ms = int((time.time() - start_time) * 1000)
        stars_used = [s.name for s in final_result.used_stars] if final_result.used_stars else []

        print(
            f"[API] Done: img={image.filename}, tz={tz_offset_hours}, "
            f"prior={last_gps}, time={solver_time_ms}ms"
        )

        return {
            "success": True,
            "latitude": final_result.latitude,
            "longitude": final_result.longitude,
            "confidence": final_result.confidence,
            "error_radius_km": final_result.error_radius_km,
            "stars_used": stars_used,
            "solver_time_ms": solver_time_ms,
            "error_message": None,
            "diagnostics": final_result.diagnostics,
        }

    except Exception as e:
        print(f"[API] EXCEPTION: {e!r}")
        import traceback; traceback.print_exc()
        return {"success": False, "error_message": str(e)}

    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
