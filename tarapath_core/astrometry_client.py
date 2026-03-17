from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import json
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _build_session() -> requests.Session:
    """Build a requests Session with retry logic and a browser-like User-Agent."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; Tarapath/0.1; +https://github.com/tarapath)",
    })
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


@dataclass
class AstrometrySource:
    ra_deg: float
    dec_deg: float
    name: Optional[str] = None
    hip: Optional[int] = None


@dataclass
class AstrometrySolution:
    success: bool
    ra_center_deg: Optional[float] = None
    dec_center_deg: Optional[float] = None
    scale_arcsec_per_pix: Optional[float] = None
    orientation_deg: Optional[float] = None
    sources: List[AstrometrySource] = None
    error_message: Optional[str] = None
    raw_result: Optional[Dict[str, Any]] = None


class AstrometryClient:
    """Minimal Astrometry.net HTTP client.

    This is intentionally thin and can be extended as needed. It assumes the
    standard JSON API as described in the Astrometry.net documentation.
    """

    def __init__(self, api_url: str, api_key: Optional[str] = None, timeout_sec: int = 600):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout_sec = timeout_sec
        self.session = _build_session()
        self.session_id: Optional[str] = None

    def _login(self) -> None:
        if not self.api_key or self.session_id:
            return
        # Astrometry.net requires the payload as a form field called 'request-json'
        resp = self.session.post(
            f"{self.api_url}/api/login",
            data={"request-json": json.dumps({"apikey": self.api_key})},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise RuntimeError(f"Astrometry login failed: {data}")
        self.session_id = data["session"]

    def solve_image(self, image_path: str) -> AstrometrySolution:
        """Submit an image and wait for the plate solution."""
        if not self.api_key:
            return AstrometrySolution(
                success=False,
                error_message=(
                    "ASTROMETRY_API_KEY is not set. "
                    "Get a free key at https://nova.astrometry.net/api_help and add it to your .env file."
                ),
            )

        try:
            self._login()
        except Exception as exc:
            return AstrometrySolution(success=False, error_message=f"Login failed: {exc}")

        if not self.session_id:
            return AstrometrySolution(
                success=False,
                error_message="Login succeeded but no session ID was returned by Astrometry.net.",
            )

        try:
            # Astrometry.net expects a multipart upload where all JSON params
            # are encoded as a string in a form field called 'request-json'.
            upload_params: Dict[str, Any] = {"session": self.session_id}
            with open(image_path, "rb") as f:
                upload_resp = self.session.post(
                    f"{self.api_url}/api/upload",
                    data={"request-json": json.dumps(upload_params)},
                    files={"file": (Path(image_path).name, f)},
                    timeout=60,
                )
            upload_resp.raise_for_status()
            upload_data = upload_resp.json()
            if upload_data.get("status") != "success":
                return AstrometrySolution(success=False, error_message=f"Upload failed: {upload_data}")

            sub_id = upload_data["subid"]

            # Poll for job id
            start = time.time()
            job_id = None
            while time.time() - start < self.timeout_sec and job_id is None:
                stat_resp = self.session.get(f"{self.api_url}/api/submissions/{sub_id}", timeout=30)
                stat_resp.raise_for_status()
                stat_data = stat_resp.json()
                jobs = stat_data.get("jobs") or []
                jobs = [j for j in jobs if j is not None]
                if jobs:
                    job_id = jobs[0]
                    break
                time.sleep(5)

            if job_id is None:
                return AstrometrySolution(success=False, error_message="Timed out waiting for Astrometry job id")

            # Poll job status
            while time.time() - start < self.timeout_sec:
                job_stat = self.session.get(f"{self.api_url}/api/jobs/{job_id}", timeout=30)
                job_stat.raise_for_status()
                job_data = job_stat.json()
                if job_data.get("status") == "success":
                    break
                if job_data.get("status") == "failure":
                    return AstrometrySolution(success=False, error_message=f"Job failed: {job_data}")
                time.sleep(10)

            # Fetch calibration data
            calib_resp = self.session.get(f"{self.api_url}/api/jobs/{job_id}/calibration", timeout=30)
            calib_resp.raise_for_status()
            calib = calib_resp.json()

            # Fetch annotations (objects)
            annot_resp = self.session.get(f"{self.api_url}/api/jobs/{job_id}/objects_in_field", timeout=30)
            annot_resp.raise_for_status()
            annot = annot_resp.json()

            sources: List[AstrometrySource] = []
            for ra, dec, name in zip(annot.get("ra", []), annot.get("dec", []), annot.get("names", [])):
                hip_id = None
                # Try to parse HIP ids from names like "HIP 12345"
                if isinstance(name, str) and name.upper().startswith("HIP"):
                    parts = name.split()
                    if len(parts) == 2 and parts[1].isdigit():
                        hip_id = int(parts[1])
                sources.append(
                    AstrometrySource(
                        ra_deg=float(ra),
                        dec_deg=float(dec),
                        name=name,
                        hip=hip_id,
                    )
                )

            return AstrometrySolution(
                success=True,
                ra_center_deg=float(calib.get("ra", 0.0)),
                dec_center_deg=float(calib.get("dec", 0.0)),
                scale_arcsec_per_pix=float(calib.get("scale", 0.0)),
                orientation_deg=float(calib.get("orientation", 0.0)),
                sources=sources,
                raw_result={"calibration": calib, "annotations": annot},
            )
        except Exception as exc:
            return AstrometrySolution(success=False, error_message=str(exc))

