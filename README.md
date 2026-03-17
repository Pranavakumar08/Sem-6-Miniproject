## Tarapath – Sky Photo Based Ship Position Estimator

Tarapath is a Python application that estimates a ship's geographic location
(latitude and longitude) from a night-sky photograph, without relying on GPS.

### High-level pipeline

- Accept a night-sky image from the user.
- Extract the capture timestamp from EXIF metadata (with manual fallback).
- Submit the image to the Astrometry.net API for plate solving.
- Cross-match identified stars against a local catalog of bright stars
  (`data/star_catalog/hyg_stars.csv`).
- Use Astropy to compute expected star Alt/Az over a grid of candidate
  Earth locations at the given timestamp.
- Find the location whose predicted star positions best match the observed
  ones and report:
  - estimated latitude / longitude,
  - confidence score,
  - confidence radius (km),
  - stars used in the fix.

### Project layout

- `tarapath_core/` – Core library (catalog, astrometry client, solver, pipeline).
- `app/` – Streamlit UI wrapping the core pipeline.
- `data/` – Input data, including `star_catalog/hyg_stars.csv`.
- `notebooks/` – Jupyter notebooks for math validation and experiments.
- `tests/` – Unit and integration tests.

### Running the project

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. (Recommended) Open and run the validation notebook in `notebooks/`
   to understand and verify the celestial navigation math.

4. Set your Astrometry.net API key in the environment:

   ```bash
   # PowerShell
   $env:ASTROMETRY_API_KEY = \"your_api_key_here\"
   ```

5. Start the Streamlit app:

   ```bash
   streamlit run app/main.py
   ```

### Accuracy and limitations

This is a GPS-independent backup system. For clear sky photos with a valid
timestamp, the target accuracy is on the order of 20–80 km. The current error
radius is derived heuristically from the solver's internal error metric and is
intended as an honest, approximate indication of uncertainty rather than a
guaranteed bound. Real-world accuracy depends strongly on image quality,
star visibility, and correct timestamps.


