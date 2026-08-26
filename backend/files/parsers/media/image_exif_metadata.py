"""SoAI - EXIF metadata extraction for images [backend/files/parsers/media/image_exif_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS
from PIL.TiffImagePlugin import IFDRational

from core.types.json import JSONDict, JSONValue
from core.validation.coercion import coerce_float_from_scalar_text_bytes

if TYPE_CHECKING:
    type ExifAtom = JSONValue | bytes | IFDRational
    type ExifSequence = list[ExifAtom] | tuple[ExifAtom, ...]
    type ExifTagValue = ExifAtom | ExifSequence | dict[int, ExifAtom | ExifSequence]

__all__ = ("apply_exif_metadata",)


def _extract_exif_fraction(value: ExifTagValue) -> tuple[int | float, int | float] | None:
    if not isinstance(value, IFDRational):
        return None
    numerator = value.numerator
    denominator = value.denominator
    if not isinstance(numerator, int | float) or not isinstance(denominator, int | float):
        return None
    return (numerator, denominator)


def _format_fraction_component(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if value.is_integer():
        return str(int(value))
    return str(value)


def _format_exposure_time(value: ExifTagValue) -> str:
    fraction = _extract_exif_fraction(value)
    if fraction is None:
        return str(value)
    numerator, denominator = fraction
    return f"{_format_fraction_component(numerator)}/{_format_fraction_component(denominator)}"


def _format_exif_rational(value: ExifTagValue, *, precision: int, suffix: str) -> str | float:
    fraction = _extract_exif_fraction(value)
    if fraction is None:
        return str(value)
    numerator, denominator = fraction
    if denominator == 0:
        return str(value)
    result = round(numerator / denominator, precision)
    if suffix:
        return f"{result}{suffix}"
    return result


def _coerce_exif_float(value: ExifTagValue) -> float | None:
    fraction = _extract_exif_fraction(value)
    if fraction is not None:
        numerator, denominator = fraction
        if denominator == 0:
            return None
        return numerator / denominator
    if value is None or isinstance(value, str | bytes | int | float | bool):
        return coerce_float_from_scalar_text_bytes(value)
    return None


def _parse_gps_coordinate(gps_info: dict[str, ExifTagValue], coord: str) -> float | None:
    key = f"GPS{coord}"
    ref_key = f"{key}Ref"
    coords_value = gps_info.get(key)
    ref_value = gps_info.get(ref_key)
    if not isinstance(coords_value, list | tuple) or len(coords_value) < 3:
        return None
    degrees = _coerce_exif_float(coords_value[0])
    minutes = _coerce_exif_float(coords_value[1])
    seconds = _coerce_exif_float(coords_value[2])
    if degrees is None or minutes is None or seconds is None:
        return None
    coord_value = degrees + minutes / 60 + seconds / 3600
    if isinstance(ref_value, str) and ref_value in ("S", "W"):
        coord_value = -coord_value
    return round(coord_value, 6)


def apply_exif_metadata(metadata: JSONDict, opened: Image.Image) -> None:
    exif_data = opened.getexif()
    try:
        exif_map: dict[int, ExifTagValue] = dict(exif_data)
    except (TypeError, ValueError):
        return
    if not exif_map:
        return
    simple_map = {
        "Make": "camera_make",
        "Model": "camera_model",
        "Software": "software",
        "ImageDescription": "description",
        "Artist": "artist",
        "Copyright": "copyright",
    }
    for tag_id, value in exif_map.items():
        tag_name = TAGS.get(tag_id) if isinstance(tag_id, int) else None
        tag = tag_name if isinstance(tag_name, str) else str(tag_id)
        if tag in simple_map:
            metadata[simple_map[tag]] = str(value).strip()
            continue
        if tag == "DateTime":
            metadata["datetime"] = str(value)
            continue
        if tag == "DateTimeOriginal":
            metadata["date_taken"] = str(value)
            continue
        if tag == "ISOSpeedRatings":
            metadata["iso"] = int(value) if isinstance(value, int | float) else str(value)
            continue
        if tag == "ExposureTime":
            metadata["exposure_time"] = _format_exposure_time(value)
            continue
        if tag == "FNumber":
            metadata["aperture"] = _format_exif_rational(value, precision=1, suffix="f")
            continue
        if tag == "FocalLength":
            metadata["focal_length"] = _format_exif_rational(value, precision=1, suffix="mm")
            continue
        if tag == "GPSInfo" and isinstance(value, dict):
            gps_info: dict[str, ExifTagValue] = {}
            for gps_tag_id, gps_value in value.items():
                gps_key = GPSTAGS.get(gps_tag_id) if isinstance(gps_tag_id, int) else None
                gps_info[gps_key or str(gps_tag_id)] = gps_value
            latitude = _parse_gps_coordinate(gps_info, "Latitude")
            if latitude is not None:
                metadata["gps_latitude"] = latitude
            longitude = _parse_gps_coordinate(gps_info, "Longitude")
            if longitude is not None:
                metadata["gps_longitude"] = longitude
            altitude = _coerce_exif_float(gps_info.get("GPSAltitude"))
            if altitude is not None:
                ref_value = gps_info.get("GPSAltitudeRef")
                if isinstance(ref_value, int) and ref_value == 1:
                    altitude = -altitude
                metadata["gps_altitude"] = round(altitude, 2)
