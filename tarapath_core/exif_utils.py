from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from pathlib import Path

from PIL import Image, ExifTags


def _get_exif(image: Image.Image):
    try:
        return image._getexif() or {}
    except Exception:
        return {}


def read_exif_datetime(path: str) -> Optional[datetime]:
    """Return capture datetime from EXIF if available."""
    img_path = Path(path)
    if not img_path.exists():
        return None

    img = Image.open(img_path)
    exif = _get_exif(img)
    if not exif:
        return None

    tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
    dt_raw = tag_map.get("DateTimeOriginal") or tag_map.get("DateTime")
    if not dt_raw:
        return None

    # Try to find exactly when this was taken relative to UTC
    # Tag 36881 is OffsetTimeOriginal, 36880 is OffsetTime
    offset_str = tag_map.get("OffsetTimeOriginal") or tag_map.get("OffsetTime") or exif.get(36881) or exif.get(36880)
    
    try:
        dt = datetime.strptime(dt_raw, "%Y:%m:%d %H:%M:%S")
        
        if offset_str and isinstance(offset_str, str) and (offset_str.startswith('+') or offset_str.startswith('-')):
            # Format: "+05:30" or "-04:00"
            sign = 1 if offset_str[0] == '+' else -1
            hours, minutes = map(int, offset_str[1:].split(':'))
            td = timedelta(hours=hours, minutes=minutes)
            tz = timezone(sign * td)
            dt = dt.replace(tzinfo=tz)
            # Normalize to pure UTC
            return dt.astimezone(timezone.utc)
        
        # If no timezone is defined in EXIF, return it as naive (local time)
        # The UI will then have to ask the user to specify the offset manually.
        return dt
    except ValueError:
        return None


def read_exif_location(path: str) -> Optional[Tuple[float, float]]:
    """Return (lat, lon) from EXIF GPS info if available."""
    img_path = Path(path)
    if not img_path.exists():
        return None

    img = Image.open(img_path)
    exif = _get_exif(img)
    if not exif:
        return None

    gps_info_tag = None
    for tag_id, value in exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, tag_id)
        if tag_name == "GPSInfo":
            gps_info_tag = value
            break

    if not gps_info_tag:
        return None

    def _convert_to_deg(value):
        d, m, s = value
        return float(d[0]) / float(d[1]) + float(m[0]) / float(m[1]) / 60.0 + float(s[0]) / float(s[1]) / 3600.0

    gps_tags = {}
    for key in gps_info_tag.keys():
        decoded = ExifTags.GPSTAGS.get(key, key)
        gps_tags[decoded] = gps_info_tag[key]

    try:
        lat = _convert_to_deg(gps_tags["GPSLatitude"])
        if gps_tags.get("GPSLatitudeRef") in ["S", "s"]:
            lat = -lat
        lon = _convert_to_deg(gps_tags["GPSLongitude"])
        if gps_tags.get("GPSLongitudeRef") in ["W", "w"]:
            lon = -lon
    except Exception:
        return None

    return lat, lon

