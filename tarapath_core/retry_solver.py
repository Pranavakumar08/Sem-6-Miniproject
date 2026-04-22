import time
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

from PIL import Image, ImageEnhance, ImageOps

from .pipeline import run_tarapath, TarapathConfig
from .types import EstimationResult
from .fallback_estimator import estimate_from_timezone


def _preprocess_image(image_path: Path, attempt: int) -> Path:
    """
    Returns path to preprocessed image for this attempt.
    Saves to tmp_uploads/preprocessed_{attempt}_{original_name}
    Cleans up previous attempt's preprocessed file.
    attempt 1: original (no change, return image_path as-is)
    attempt 2: grayscale
    attempt 3: resize to 1024x1024
    attempt 4: brightness +50%
    attempt 5: contrast +1.5x
    """
    if attempt == 1:
        return image_path

    # Clean up previous attempt
    if attempt > 2:
        prev_path = image_path.parent / f"preprocessed_{attempt - 1}_{image_path.name}"
        if prev_path.exists():
            prev_path.unlink()

    out_path = image_path.parent / f"preprocessed_{attempt}_{image_path.name}"
    
    with Image.open(image_path) as img:
        # Convert to RGB to safely apply enhancements
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        if attempt == 2:
            img = ImageOps.grayscale(img)
        elif attempt == 3:
            img = img.resize((1024, 1024), Image.Resampling.LANCZOS)
        elif attempt == 4:
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.5)
        elif attempt == 5:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)
            
        img.save(out_path)
    
    return out_path


def solve_with_retries(
    image_path: Path,
    timestamp_override: datetime,
    config: TarapathConfig,
    tz_offset_hours: float,
    max_attempts: int = 5,
    delay_seconds: int = 60,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> EstimationResult:
    """
    Try tetra3 solve up to max_attempts times with different image
    preprocessing on each attempt.
    If all attempts fail, fall back to estimate_from_timezone().
    Calls progress_callback(message) before each attempt so Streamlit
    can show live updates.
    """
    for attempt in range(1, max_attempts + 1):
        if progress_callback:
            if attempt == 1:
                progress_callback("⏳ Plate solving via tetra3 (offline)... [Attempt 1]")
            else:
                progress_callback(f"⏳ Attempt {attempt}/{max_attempts}: Processing image with new settings...")
            
        preprocessed_path = _preprocess_image(image_path, attempt)
        
        # Plate solve
        result = run_tarapath(
            str(preprocessed_path),
            timestamp_override=timestamp_override,
            config=config,
        )
        
        if not result.error_message:
            # Clean up the last preprocessed image if we succeeded
            if preprocessed_path != image_path and preprocessed_path.exists():
                preprocessed_path.unlink()
            return result
            
        # Failed, wait if we have more attempts
        if attempt < max_attempts:
            if progress_callback:
                progress_callback(f"⚠️ Attempt {attempt} failed. Waiting {delay_seconds}s before next attempt...")
            time.sleep(delay_seconds)
            
        # Clean up the preprocessed image on failure too if it's the last attempt
        if attempt == max_attempts and preprocessed_path != image_path and preprocessed_path.exists():
            preprocessed_path.unlink()

    if progress_callback:
        progress_callback("❌ All attempts failed. Using timezone fallback...")
        
    return estimate_from_timezone(
        tz_offset_hours=tz_offset_hours,
        timestamp=timestamp_override,
    )
