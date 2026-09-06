"""
Metocean Vector Mathematics and Physical Conventions.

Smart India Hackathon 2026 - Problem Statement 26143.

CONVENTIONS DOCUMENTATION:
-------------------------
1. METEOROLOGICAL WIND CONVENTION:
   - Wind direction (theta_from) is the azimuth angle measured in degrees clockwise from
     True North (0° = North, 90° = East, 180° = South, 270° = West) FROM which the wind is blowing.
   - The direction the wind blows TOWARDS is theta_to = (theta_from + 180°) % 360°.
   - Mathematical coordinate system: x-axis points East (u), y-axis points North (v).
   - Component equations:
       u = speed * sin(theta_to) = -speed * sin(theta_from)
       v = speed * cos(theta_to) = -speed * cos(theta_from)
   - Inverse conversion:
       speed = sqrt(u^2 + v^2)
       theta_from = (atan2(-u, -v) * 180 / pi + 360°) % 360°

2. OCEANOGRAPHIC CURRENT CONVENTION:
   - Current direction (theta_to) is the azimuth angle measured in degrees clockwise from
     True North (0° = North, 90° = East, 180° = South, 270° = West) TOWARDS which the water is setting/flowing.
   - Component equations:
       u = speed * sin(theta_to)
       v = speed * cos(theta_to)
   - Inverse conversion:
       speed = sqrt(u^2 + v^2)
       theta_to = (atan2(u, v) * 180 / pi + 360°) % 360°

3. UNITS:
   - Velocity components (u, v): meters per second (m/s)
   - Speeds: meters per second (m/s)
   - Angles: decimal degrees True North [0.0, 360.0)
"""

import math
from typing import Tuple


def wind_speed_dir_to_uv(speed_ms: float, direction_deg_from: float) -> Tuple[float, float]:
    """
    Convert meteorological wind speed (m/s) and direction FROM (degrees True)
    into eastward (u) and northward (v) velocity components (m/s).
    """
    if speed_ms < 0:
        raise ValueError(f"Wind speed cannot be negative: {speed_ms}")

    rad = math.radians(direction_deg_from % 360.0)
    # Wind blowing FROM direction means velocity vector is opposite:
    u = -speed_ms * math.sin(rad)
    v = -speed_ms * math.cos(rad)
    return round(float(u), 4), round(float(v), 4)


def uv_to_wind_speed_dir(u: float, v: float) -> Tuple[float, float]:
    """
    Convert eastward (u) and northward (v) wind components (m/s)
    into scalar wind speed (m/s) and meteorological direction FROM (degrees True).
    """
    speed = math.sqrt(u**2 + v**2)
    if math.isclose(speed, 0.0, abs_tol=1e-7):
        return 0.0, 0.0

    deg = (math.atan2(-u, -v) * 180.0 / math.pi + 360.0) % 360.0
    return round(float(speed), 2), round(float(deg), 1)


def current_speed_dir_to_uv(speed_ms: float, direction_deg_to: float) -> Tuple[float, float]:
    """
    Convert oceanographic current speed (m/s) and direction TOWARDS (degrees True)
    into eastward (u) and northward (v) velocity components (m/s).
    """
    if speed_ms < 0:
        raise ValueError(f"Current speed cannot be negative: {speed_ms}")

    rad = math.radians(direction_deg_to % 360.0)
    u = speed_ms * math.sin(rad)
    v = speed_ms * math.cos(rad)
    return round(float(u), 4), round(float(v), 4)


def uv_to_current_speed_dir(u: float, v: float) -> Tuple[float, float]:
    """
    Convert eastward (u) and northward (v) current components (m/s)
    into scalar current speed (m/s) and oceanographic direction TOWARDS (degrees True).
    """
    speed = math.sqrt(u**2 + v**2)
    if math.isclose(speed, 0.0, abs_tol=1e-7):
        return 0.0, 0.0

    deg = (math.atan2(u, v) * 180.0 / math.pi + 360.0) % 360.0
    return round(float(speed), 3), round(float(deg), 1)


def knots_to_ms(knots: float) -> float:
    """Convert nautical miles per hour (knots) to meters per second (m/s)."""
    return round(knots * 0.514444, 4)


def ms_to_knots(ms: float) -> float:
    """Convert meters per second (m/s) to nautical miles per hour (knots)."""
    return round(ms / 0.514444, 2)


def kmh_to_ms(kmh: float) -> float:
    """Convert kilometers per hour (km/h) to meters per second (m/s)."""
    return round(kmh / 3.6, 4)


def ms_to_kmh(ms: float) -> float:
    """Convert meters per second (m/s) to kilometers per hour (km/h)."""
    return round(ms * 3.6, 2)
