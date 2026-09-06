import math
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union

import numpy as np

from backend.app.domain.models import (
    AISPoint,
    AISTrajectory,
    CoordinatePoint,
    SpillGeometry,
    ReleaseTimeWindow,
    SpeedStatistics,
    CourseStatistics,
    RouteDeviation,
    AISGap,
    CandidateVesselFeatures,
)
from backend.app.adapters.ais.ais_adapter import AISAdapter

logger = logging.getLogger(__name__)

# Geodetic constants
EARTH_RADIUS_KM = 6371.0
KM_PER_NAUTICAL_MILE = 1.852
METERS_PER_DEGREE_LAT = 111320.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Great-Circle geodetic distance between two WGS84 points in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_KM * c, 4)


def calculate_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial nautical forward azimuth (bearing) from Point 1 to Point 2 in degrees [0, 360)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)

    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    bearing = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return round(bearing, 1)


def angular_difference_deg(angle1: float, angle2: float) -> float:
    """Smallest positive difference between two angles in degrees [0, 180]."""
    diff = abs(angle1 - angle2) % 360.0
    return round(360.0 - diff if diff > 180.0 else diff, 2)


def point_in_polygon(lon: float, lat: float, polygon_ring: List[List[float]]) -> bool:
    """
    Ray-casting algorithm to determine if point (lon, lat) is inside a GeoJSON polygon ring.
    polygon_ring: List of [lon, lat] coordinate pairs.
    """
    if len(polygon_ring) < 3:
        return False

    inside = False
    n = len(polygon_ring)
    for i in range(n):
        j = (i + 1) % n
        xi, yi = polygon_ring[i][0], polygon_ring[i][1]
        xj, yj = polygon_ring[j][0], polygon_ring[j][1]

        # Check if ray crosses edge
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
    return inside


def segments_intersect(
    p1: Tuple[float, float], p2: Tuple[float, float],
    p3: Tuple[float, float], p4: Tuple[float, float]
) -> bool:
    """
    Check if 2D line segment (p1 -> p2) intersects segment (p3 -> p4).
    Each point is (lon, lat).
    """
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))


class AISVesselAnalyzer:
    """
    AIS Vessel Trajectory Analysis & Kinematic Feature Extraction Engine.
    
    Processes historical AIS tracks to extract forensic evidence features
    near a probable oil spill source region and release-time window.
    
    IMPORTANT SCIENTIFIC PRINCIPLE:
    This engine extracts objective spatial and behavioral features.
    It does NOT identify or declare a vessel as responsible.
    """

    def __init__(
        self,
        max_speed_knots: float = 60.0,
        teleportation_threshold_knots: float = 65.0,
        gap_threshold_hours: float = 1.0,
        temporal_buffer_hours: float = 3.0,
    ):
        self.max_speed_knots = max_speed_knots
        self.teleportation_threshold_knots = teleportation_threshold_knots
        self.gap_threshold_hours = gap_threshold_hours
        self.temporal_buffer_hours = temporal_buffer_hours
        self._adapter = AISAdapter()

    # =========================================================================
    # 1. Normalization & Sanitization
    # =========================================================================

    def normalize_timestamp(self, ts_input: Union[str, datetime, float, int]) -> Optional[datetime]:
        """Normalize various timestamp formats into a UTC-aware datetime object."""
        if isinstance(ts_input, datetime):
            if ts_input.tzinfo is None:
                return ts_input.replace(tzinfo=timezone.utc)
            return ts_input.astimezone(timezone.utc)

        if isinstance(ts_input, (int, float)):
            try:
                # Distinguish seconds vs milliseconds epoch
                epoch_sec = ts_input if ts_input < 1e11 else ts_input / 1000.0
                return datetime.fromtimestamp(epoch_sec, tz=timezone.utc)
            except Exception:
                return None

        if isinstance(ts_input, str):
            clean = ts_input.strip().replace("Z", "+00:00")
            for fmt in (
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%d %H:%M:%S.%f%z",
            ):
                try:
                    return datetime.strptime(clean, fmt).astimezone(timezone.utc)
                except ValueError:
                    continue

            # Fallback to fromisoformat
            try:
                dt = datetime.fromisoformat(clean)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                return None

        return None

    def sanitize_pings(self, raw_pings: List[Dict[str, Any]]) -> Tuple[List[AISPoint], int, int]:
        """
        Filter out invalid coordinates and physically impossible speeds.
        
        Rules:
          - Valid latitude: -90.0 <= lat <= 90.0
          - Valid longitude: -180.0 <= lon <= 180.0
          - Rejects (0, 0) GPS origin nulls
          - Rejects NaNs / Infs
          - Rejects SOG < 0 or SOG > max_speed_knots (60 kn)
          - Rejects kinematic teleportation jumps
        
        Returns:
          (sanitized_points, total_raw_count, rejected_count)
        """
        raw_count = len(raw_pings)
        rejected_count = 0
        points_by_mmsi: Dict[str, List[AISPoint]] = {}

        for p in raw_pings:
            mmsi = str(p.get("mmsi") or p.get("MMSI") or "").strip()
            if not mmsi:
                rejected_count += 1
                continue

            raw_time = p.get("timestamp") or p.get("BaseDateTime") or p.get("time")
            ts = self.normalize_timestamp(raw_time)
            if ts is None:
                rejected_count += 1
                continue

            try:
                lat = float(p.get("latitude") if p.get("latitude") is not None else (p.get("LAT") or p.get("lat") or 0.0))
                lon = float(p.get("longitude") if p.get("longitude") is not None else (p.get("LON") or p.get("lon") or 0.0))
                speed = float(p.get("speed") if p.get("speed") is not None else (p.get("SOG") or p.get("sog") or 0.0))
                course = float(p.get("course") if p.get("course") is not None else (p.get("COG") or p.get("cog") or 0.0))
            except (ValueError, TypeError):
                rejected_count += 1
                continue

            # Coordinate range check
            if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
                rejected_count += 1
                continue
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                rejected_count += 1
                continue

            # Reject GPS null coordinate (0, 0)
            if abs(lat) < 1e-5 and abs(lon) < 1e-5:
                rejected_count += 1
                continue

            # Impossible instantaneous speed check
            if speed < 0.0 or speed > self.max_speed_knots:
                rejected_count += 1
                continue

            # Course check
            course = (course % 360.0)

            # Heading check
            raw_heading = p.get("heading") or p.get("Heading")
            heading = None
            if raw_heading not in (None, "", "511", "511.0", 511):
                try:
                    h = float(raw_heading)
                    if 0.0 <= h < 360.0:
                        heading = h
                except ValueError:
                    pass

            vessel_name = p.get("vessel_name") or p.get("VesselName")
            vessel_type = p.get("vessel_type") or p.get("VesselType")
            imo = p.get("imo") or p.get("IMO")
            callsign = p.get("callsign") or p.get("CallSign")

            point = AISPoint(
                mmsi=mmsi,
                timestamp=ts,
                latitude=round(lat, 5),
                longitude=round(lon, 5),
                speed=round(speed, 2),
                course=round(course, 1),
                heading=heading,
                vessel_name=vessel_name,
                vessel_type=vessel_type,
                imo=imo,
                callsign=callsign,
            )

            if mmsi not in points_by_mmsi:
                points_by_mmsi[mmsi] = []
            points_by_mmsi[mmsi].append(point)

        # Kinematic Jump & Teleportation Filter per vessel
        sanitized_points: List[AISPoint] = []
        for mmsi, mmsi_pts in points_by_mmsi.items():
            # Sort chronologically
            mmsi_pts.sort(key=lambda pt: pt.timestamp)

            valid_mmsi_pts: List[AISPoint] = []
            for i, pt in enumerate(mmsi_pts):
                if not valid_mmsi_pts:
                    valid_mmsi_pts.append(pt)
                    continue

                prev = valid_mmsi_pts[-1]
                dt_hours = (pt.timestamp - prev.timestamp).total_seconds() / 3600.0

                if dt_hours <= 0.0:
                    # Duplicate or out-of-order ping
                    rejected_count += 1
                    continue

                # Check for kinematic teleportation jumps
                if dt_hours < 2.0:
                    dist_km = haversine_distance_km(prev.latitude, prev.longitude, pt.latitude, pt.longitude)
                    dist_nm = dist_km / KM_PER_NAUTICAL_MILE
                    kinematic_speed = dist_nm / dt_hours
                    if kinematic_speed > self.teleportation_threshold_knots:
                        logger.warning(
                            f"Kinematic teleportation jump detected for MMSI {mmsi}: "
                            f"{kinematic_speed:.1f} knots over {dt_hours*60:.1f} min. Discarding ping."
                        )
                        rejected_count += 1
                        continue

                valid_mmsi_pts.append(pt)

            sanitized_points.extend(valid_mmsi_pts)

        return sanitized_points, raw_count, rejected_count

    # =========================================================================
    # 2. Trajectory Reconstruction
    # =========================================================================

    def reconstruct_trajectories(self, points: List[AISPoint]) -> List[AISTrajectory]:
        """Group points by MMSI, sort chronologically, and identify AIS gaps."""
        grouped: Dict[str, List[AISPoint]] = {}
        names: Dict[str, str] = {}
        types: Dict[str, str] = {}

        for pt in points:
            if pt.mmsi not in grouped:
                grouped[pt.mmsi] = []
            grouped[pt.mmsi].append(pt)
            if pt.vessel_name:
                names[pt.mmsi] = pt.vessel_name
            if pt.vessel_type:
                types[pt.mmsi] = pt.vessel_type

        trajectories: List[AISTrajectory] = []
        for mmsi, pts in grouped.items():
            pts.sort(key=lambda p: p.timestamp)

            gaps_count = 0
            for i in range(1, len(pts)):
                delta = pts[i].timestamp - pts[i - 1].timestamp
                if delta > timedelta(hours=self.gap_threshold_hours):
                    gaps_count += 1

            trajectories.append(
                AISTrajectory(
                    mmsi=mmsi,
                    vessel_name=names.get(mmsi, f"Vessel-{mmsi}"),
                    vessel_type=types.get(mmsi, "Unknown"),
                    points=pts,
                    interpolated=False,
                    data_gaps_count=gaps_count,
                )
            )

        return trajectories

    # =========================================================================
    # 3. Spatial & Temporal Filtering
    # =========================================================================

    def filter_candidates(
        self,
        trajectories: List[AISTrajectory],
        source_centroid: CoordinatePoint,
        release_window: ReleaseTimeWindow,
        spatial_radius_km: float,
    ) -> List[AISTrajectory]:
        """
        Filter trajectories down to candidates that navigated within
        spatial_radius_km of the source centroid and overlap the release time window.
        """
        earliest_limit = self.normalize_timestamp(release_window.earliest) - timedelta(hours=self.temporal_buffer_hours)
        latest_limit = self.normalize_timestamp(release_window.latest) + timedelta(hours=self.temporal_buffer_hours)

        candidates: List[AISTrajectory] = []
        for traj in trajectories:
            pts = traj.points
            if not pts:
                continue

            t_start = pts[0].timestamp
            t_end = pts[-1].timestamp

            # 1. Temporal filter
            if t_end < earliest_limit or t_start > latest_limit:
                continue

            # 2. Spatial filter (must come within spatial_radius_km at least once)
            min_dist = min(
                haversine_distance_km(p.latitude, p.longitude, source_centroid.latitude, source_centroid.longitude)
                for p in pts
            )

            if min_dist <= spatial_radius_km:
                candidates.append(traj)

        return candidates

    # =========================================================================
    # 4. Closest Point of Approach (CPA) & Dwell Time
    # =========================================================================

    def compute_cpa(
        self,
        trajectory: AISTrajectory,
        source_centroid: CoordinatePoint,
    ) -> Tuple[CoordinatePoint, float, datetime, int]:
        """
        Calculate Closest Point of Approach (CPA) from trajectory to source centroid.
        
        Returns:
          (closest_point, closest_distance_km, time_of_cpa, cpa_point_index)
        """
        pts = trajectory.points
        best_idx = 0
        min_dist = float("inf")

        for i, pt in enumerate(pts):
            d = haversine_distance_km(pt.latitude, pt.longitude, source_centroid.latitude, source_centroid.longitude)
            if d < min_dist:
                min_dist = d
                best_idx = i

        cpa_pt = pts[best_idx]
        closest_coord = CoordinatePoint(latitude=cpa_pt.latitude, longitude=cpa_pt.longitude)
        return closest_coord, min_dist, cpa_pt.timestamp, best_idx

    def compute_entry_exit_and_dwell(
        self,
        trajectory: AISTrajectory,
        source_centroid: CoordinatePoint,
        spatial_radius_km: float,
        source_polygon_ring: Optional[List[List[float]]] = None,
    ) -> Tuple[Optional[datetime], Optional[datetime], float]:
        """
        Calculate entry time, exit time, and dwell time (minutes) within the spatial radius
        or source polygon boundary.
        """
        pts = trajectory.points
        in_zone_indices = []

        for i, pt in enumerate(pts):
            d = haversine_distance_km(pt.latitude, pt.longitude, source_centroid.latitude, source_centroid.longitude)
            is_near = (d <= spatial_radius_km)
            if not is_near and source_polygon_ring:
                is_near = point_in_polygon(pt.longitude, pt.latitude, source_polygon_ring)

            if is_near:
                in_zone_indices.append(i)

        if not in_zone_indices:
            return None, None, 0.0

        entry_time = pts[in_zone_indices[0]].timestamp
        exit_time = pts[in_zone_indices[-1]].timestamp

        if len(in_zone_indices) == 1:
            # Single ping near source: estimate duration based on transit time to adjacent pings
            idx = in_zone_indices[0]
            dt_est = 10.0  # default 10 minutes
            if idx > 0 and idx < len(pts) - 1:
                dt_total = (pts[idx + 1].timestamp - pts[idx - 1].timestamp).total_seconds() / 60.0
                dt_est = min(60.0, max(5.0, dt_total * 0.5))
            dwell_minutes = round(dt_est, 1)
        else:
            dwell_minutes = round((exit_time - entry_time).total_seconds() / 60.0, 1)

        return entry_time, exit_time, dwell_minutes

    # =========================================================================
    # 5. Point-in-Polygon & Segment Crossings
    # =========================================================================

    def check_source_region_intersection(
        self,
        trajectory: AISTrajectory,
        source_polygon_ring: List[List[float]],
    ) -> bool:
        """
        Determine if vessel traversed through the probable source polygon.
        Performs both point-in-polygon tests and trajectory segment boundary crossings.
        """
        if not source_polygon_ring or len(source_polygon_ring) < 3:
            return False

        pts = trajectory.points
        # 1. Point-in-polygon check for all pings
        for pt in pts:
            if point_in_polygon(pt.longitude, pt.latitude, source_polygon_ring):
                return True

        # 2. Segment intersection check
        m = len(source_polygon_ring)
        for i in range(1, len(pts)):
            p1 = (pts[i - 1].longitude, pts[i - 1].latitude)
            p2 = (pts[i].longitude, pts[i].latitude)

            for j in range(m):
                k = (j + 1) % m
                poly_edge_1 = (source_polygon_ring[j][0], source_polygon_ring[j][1])
                poly_edge_2 = (source_polygon_ring[k][0], source_polygon_ring[k][1])

                if segments_intersect(p1, p2, poly_edge_1, poly_edge_2):
                    return True

        return False

    # =========================================================================
    # 6. Direction & Kinematic Statistics
    # =========================================================================

    def compute_approach_and_departure_directions(
        self,
        trajectory: AISTrajectory,
        cpa_idx: int,
    ) -> Tuple[float, float]:
        """
        Compute nautical approach and departure directions (degrees [0, 360)) at CPA.
        """
        pts = trajectory.points
        n = len(pts)

        # Approach direction (towards CPA)
        if cpa_idx > 0:
            approach_deg = calculate_bearing_deg(
                pts[cpa_idx - 1].latitude, pts[cpa_idx - 1].longitude,
                pts[cpa_idx].latitude, pts[cpa_idx].longitude,
            )
        elif pts[cpa_idx].course is not None:
            approach_deg = pts[cpa_idx].course
        elif n > 1:
            approach_deg = calculate_bearing_deg(
                pts[0].latitude, pts[0].longitude,
                pts[1].latitude, pts[1].longitude,
            )
        else:
            approach_deg = 0.0

        # Departure direction (away from CPA)
        if cpa_idx < n - 1:
            departure_deg = calculate_bearing_deg(
                pts[cpa_idx].latitude, pts[cpa_idx].longitude,
                pts[cpa_idx + 1].latitude, pts[cpa_idx + 1].longitude,
            )
        elif pts[cpa_idx].course is not None:
            departure_deg = pts[cpa_idx].course
        elif n > 1:
            departure_deg = calculate_bearing_deg(
                pts[-2].latitude, pts[-2].longitude,
                pts[-1].latitude, pts[-1].longitude,
            )
        else:
            departure_deg = 0.0

        return round(approach_deg, 1), round(departure_deg, 1)

    def compute_speed_statistics(
        self,
        trajectory: AISTrajectory,
        cpa_idx: int,
    ) -> SpeedStatistics:
        """Calculate mean, min, max, std, speed at CPA, and speed drop."""
        speeds = [p.speed for p in trajectory.points]
        cpa_speed = trajectory.points[cpa_idx].speed

        mean_spd = float(np.mean(speeds))
        min_spd = float(np.min(speeds))
        max_spd = float(np.max(speeds))
        std_spd = float(np.std(speeds)) if len(speeds) > 1 else 0.0

        # Transit baseline speed before CPA
        pre_cpa_speeds = [p.speed for i, p in enumerate(trajectory.points) if i < cpa_idx]
        baseline_speed = float(np.mean(pre_cpa_speeds)) if pre_cpa_speeds else mean_spd

        speed_drop = max(0.0, baseline_speed - cpa_speed)
        speed_drop_pct = (speed_drop / baseline_speed * 100.0) if baseline_speed > 0.5 else 0.0

        return SpeedStatistics(
            mean_speed_knots=round(mean_spd, 2),
            min_speed_knots=round(min_spd, 2),
            max_speed_knots=round(max_spd, 2),
            std_speed_knots=round(std_spd, 2),
            speed_at_cpa_knots=round(cpa_speed, 2),
            speed_drop_knots=round(speed_drop, 2),
            speed_drop_percent=round(speed_drop_pct, 1),
        )

    def compute_course_statistics(
        self,
        trajectory: AISTrajectory,
    ) -> CourseStatistics:
        """Compute circular mean, circular dispersion, and max course alterations."""
        courses = [p.course for p in trajectory.points]
        n = len(courses)

        if n == 0:
            return CourseStatistics(
                mean_course_deg=0.0,
                std_course_deg=0.0,
                min_course_deg=0.0,
                max_course_deg=0.0,
                max_course_change_deg=0.0,
            )

        # Circular mean
        sin_sum = sum(math.sin(math.radians(c)) for c in courses)
        cos_sum = sum(math.cos(math.radians(c)) for c in courses)
        mean_c = (math.degrees(math.atan2(sin_sum, cos_sum)) + 360.0) % 360.0

        # Circular standard deviation
        R = math.sqrt(sin_sum**2 + cos_sum**2) / n
        R = min(1.0, max(1e-6, R))
        std_c = math.sqrt(-2.0 * math.log(R)) * (180.0 / math.pi)

        # Max course change between consecutive points
        max_change = 0.0
        for i in range(1, n):
            d = angular_difference_deg(courses[i], courses[i - 1])
            if d > max_change:
                max_change = d

        return CourseStatistics(
            mean_course_deg=round(mean_c, 1),
            std_course_deg=round(std_c, 1),
            min_course_deg=round(float(np.min(courses)), 1),
            max_course_deg=round(float(np.max(courses)), 1),
            max_course_change_deg=round(max_change, 1),
        )

    # =========================================================================
    # 7. Route Deviation & AIS Gap Detection
    # =========================================================================

    def detect_route_deviation(
        self,
        trajectory: AISTrajectory,
        cpa_idx: int,
        speed_stats: SpeedStatistics,
        course_stats: CourseStatistics,
    ) -> RouteDeviation:
        """
        Detect route deviations, loitering, speed drops, or sharp turns near the source region.
        Requires sufficient trajectory history (>= 3 points) to establish baseline.
        """
        pts = trajectory.points
        if len(pts) < 3:
            return RouteDeviation(
                detected=False,
                deviation_type="NONE",
                description="Insufficient trajectory points (< 3) to establish route deviation baseline.",
                heading_change_deg=0.0,
                speed_reduction_ratio=0.0,
            )

        # 1. Course alteration near CPA
        cpa_heading_change = 0.0
        if cpa_idx > 0 and cpa_idx < len(pts) - 1:
            cpa_heading_change = angular_difference_deg(pts[cpa_idx - 1].course, pts[cpa_idx + 1].course)

        # 2. Speed drop ratio
        speed_reduction = speed_stats.speed_drop_percent / 100.0

        # 3. Loitering check (slow speed <= 3.0 kn during encounter)
        is_loitering = (speed_stats.speed_at_cpa_knots <= 3.0 and speed_stats.mean_speed_knots < 5.0)

        if is_loitering:
            return RouteDeviation(
                detected=True,
                deviation_type="LOITERING",
                description=(
                    f"Vessel maintained near-zero speed ({speed_stats.speed_at_cpa_knots:.1f} kn) "
                    f"indicating stationary or loitering behavior near source region."
                ),
                heading_change_deg=round(course_stats.max_course_change_deg, 1),
                speed_reduction_ratio=round(speed_reduction, 2),
            )

        if speed_reduction >= 0.30 and speed_stats.speed_drop_knots >= 3.0:
            return RouteDeviation(
                detected=True,
                deviation_type="SPEED_DECELERATION",
                description=(
                    f"Significant speed drop of {speed_stats.speed_drop_knots:.1f} kn "
                    f"({speed_stats.speed_drop_percent:.0f}% deceleration) observed at Closest Point of Approach."
                ),
                heading_change_deg=round(cpa_heading_change, 1),
                speed_reduction_ratio=round(speed_reduction, 2),
            )

        if cpa_heading_change >= 25.0 or course_stats.max_course_change_deg >= 35.0:
            change_deg = max(cpa_heading_change, course_stats.max_course_change_deg)
            return RouteDeviation(
                detected=True,
                deviation_type="SHARP_COURSE_CHANGE",
                description=(
                    f"Course alteration of {change_deg:.1f}° detected along trajectory "
                    f"deviating from standard straight transit track."
                ),
                heading_change_deg=round(change_deg, 1),
                speed_reduction_ratio=round(speed_reduction, 2),
            )

        return RouteDeviation(
            detected=False,
            deviation_type="NONE",
            description="Vessel maintained consistent speed and steady track corridor.",
            heading_change_deg=round(course_stats.max_course_change_deg, 1),
            speed_reduction_ratio=round(speed_reduction, 2),
        )

    def detect_ais_gaps(
        self,
        trajectory: AISTrajectory,
        release_window: ReleaseTimeWindow,
    ) -> AISGap:
        """
        Inspect trajectory for significant AIS transmission blackouts (> 1 hour)
        overlapping or adjacent to the oil release window.
        """
        pts = trajectory.points
        if len(pts) < 2:
            return AISGap(detected=False, gap_duration_minutes=0.0)

        earliest = self.normalize_timestamp(release_window.earliest) - timedelta(hours=2.0)
        latest = self.normalize_timestamp(release_window.latest) + timedelta(hours=2.0)

        max_gap_sec = 0.0
        gap_start = None
        gap_end = None

        for i in range(1, len(pts)):
            t_prev = pts[i - 1].timestamp
            t_curr = pts[i].timestamp
            dt_sec = (t_curr - t_prev).total_seconds()

            if dt_sec > (self.gap_threshold_hours * 3600.0):
                # Check if gap intersects window
                if max(t_prev, earliest) <= min(t_curr, latest):
                    if dt_sec > max_gap_sec:
                        max_gap_sec = dt_sec
                        gap_start = t_prev
                        gap_end = t_curr

        if max_gap_sec > 0.0:
            mins = round(max_gap_sec / 60.0, 1)
            return AISGap(
                detected=True,
                gap_duration_minutes=mins,
                gap_start_time=gap_start,
                gap_end_time=gap_end,
                description=f"AIS transponder silence of {mins:.0f} minutes detected near release window.",
            )

        return AISGap(detected=False, gap_duration_minutes=0.0)

    # =========================================================================
    # 8. Complete Multi-Vessel Analysis Pipeline
    # =========================================================================

    def analyze_candidates(
        self,
        probable_source_region: Union[SpillGeometry, Dict[str, Any], List[List[float]]],
        release_time_window: ReleaseTimeWindow,
        spatial_radius_km: float = 25.0,
        ais_dataset: Union[Path, str, List[AISTrajectory], List[Dict[str, Any]]] = None,
        source_centroid: Optional[CoordinatePoint] = None,
    ) -> List[CandidateVesselFeatures]:
        """
        Execute complete 10-step AIS trajectory analysis and kinematic feature extraction.
        
        Inputs:
          - probable_source_region: GeoJSON SpillGeometry or list of [lon, lat] ring coordinates
          - release_time_window: ReleaseTimeWindow bracket
          - spatial_radius_km: Configurable search distance threshold
          - ais_dataset: Filepath (CSV), list of AISTrajectory, or list of raw ping dicts
          - source_centroid: Optional spatial center of mass
        
        Returns:
          List[CandidateVesselFeatures] for all candidate vessels meeting spatial/temporal criteria.
        """
        # Parse source polygon ring and centroid
        polygon_ring: List[List[float]] = []
        if isinstance(probable_source_region, SpillGeometry):
            if probable_source_region.coordinates and len(probable_source_region.coordinates) > 0:
                coords = probable_source_region.coordinates
                polygon_ring = coords[0] if isinstance(coords[0][0], list) else coords
        elif isinstance(probable_source_region, dict):
            coords = probable_source_region.get("coordinates", [])
            if coords and len(coords) > 0:
                polygon_ring = coords[0] if isinstance(coords[0][0], list) else coords
        elif isinstance(probable_source_region, list):
            polygon_ring = probable_source_region

        if source_centroid is None:
            if polygon_ring and len(polygon_ring) >= 3:
                # Arithmetic centroid
                lons = [p[0] for p in polygon_ring]
                lats = [p[1] for p in polygon_ring]
                source_centroid = CoordinatePoint(
                    latitude=round(float(np.mean(lats)), 4),
                    longitude=round(float(np.mean(lons)), 4),
                )
            else:
                raise ValueError("source_centroid or a valid probable_source_region polygon is required.")

        # Load & Ingest raw data
        raw_pings: List[Dict[str, Any]] = []
        pre_trajectories: Optional[List[AISTrajectory]] = None

        if isinstance(ais_dataset, (str, Path)):
            p = Path(ais_dataset)
            if not p.exists():
                raise FileNotFoundError(f"AIS dataset file not found: {p}")
            pre_trajectories = self._adapter.load_from_csv(p)
        elif isinstance(ais_dataset, list):
            if ais_dataset and isinstance(ais_dataset[0], AISTrajectory):
                pre_trajectories = ais_dataset
            elif ais_dataset and isinstance(ais_dataset[0], AISPoint):
                raw_pings = [pt.model_dump() for pt in ais_dataset]
            elif ais_dataset and isinstance(ais_dataset[0], dict):
                raw_pings = ais_dataset
        elif ais_dataset is None:
            # Fallback to demo fixture
            fixture_path = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "marine_cadastre_ais_fixture.csv"
            if fixture_path.exists():
                pre_trajectories = self._adapter.load_from_csv(fixture_path)
            else:
                raise ValueError("No AIS dataset provided and default fixture not found.")

        # If pre_trajectories exists, extract raw pings to run standard sanitization
        if pre_trajectories is not None:
            for traj in pre_trajectories:
                for pt in traj.points:
                    raw_pings.append(pt.model_dump())

        # Step 1, 2, 3: Normalize timestamps, reject invalid coords & impossible speeds
        sanitized_pings, total_raw_count, total_rejected_count = self.sanitize_pings(raw_pings)

        # Step 4: Reconstruct vessel trajectories
        trajectories = self.reconstruct_trajectories(sanitized_pings)

        # Step 5 & 6: Spatial & Temporal Filtering
        candidates = self.filter_candidates(
            trajectories=trajectories,
            source_centroid=source_centroid,
            release_window=release_time_window,
            spatial_radius_km=spatial_radius_km,
        )

        logger.info(
            f"AIS Vessel Analysis: {len(trajectories)} trajectories reconstructed, "
            f"{len(candidates)} candidates retained within {spatial_radius_km} km corridor."
        )

        results: List[CandidateVesselFeatures] = []
        for cand in candidates:
            # Step 7: Closest Point of Approach (CPA)
            closest_coord, min_dist, cpa_time, cpa_idx = self.compute_cpa(cand, source_centroid)

            # Entry, Exit, Dwell Time
            entry_t, exit_t, dwell_mins = self.compute_entry_exit_and_dwell(
                cand, source_centroid, spatial_radius_km, polygon_ring
            )

            # Step 8: Source Region Point-in-Polygon & Segment Intersection
            passed_polygon = self.check_source_region_intersection(cand, polygon_ring)

            # Step 9: Approach & Departure Direction
            approach_deg, departure_deg = self.compute_approach_and_departure_directions(cand, cpa_idx)

            # Step 10: Speed & Course Behavior Statistics
            speed_stats = self.compute_speed_statistics(cand, cpa_idx)
            course_stats = self.compute_course_statistics(cand)

            # Route Deviation Indicator
            route_dev = self.detect_route_deviation(cand, cpa_idx, speed_stats, course_stats)

            # AIS Dark Gap Indicator
            ais_gap = self.detect_ais_gaps(cand, release_time_window)

            cand_raw_count = len([p for p in raw_pings if str(p.get("mmsi") or p.get("MMSI")) == cand.mmsi])
            cand_sanitized_count = len(cand.points)

            features = CandidateVesselFeatures(
                mmsi=cand.mmsi,
                vessel_name=cand.vessel_name,
                vessel_type=cand.vessel_type,
                imo=cand.points[0].imo if cand.points else None,
                callsign=cand.points[0].callsign if cand.points else None,
                trajectory=cand,
                closest_point_to_source=closest_coord,
                closest_distance_km=round(min_dist, 2),
                time_of_closest_approach=cpa_time,
                passed_through_source_region=passed_polygon,
                time_spent_near_source_minutes=dwell_mins,
                entry_time=entry_t,
                exit_time=exit_t,
                speed_statistics=speed_stats,
                course_statistics=course_stats,
                approach_direction_deg=approach_deg,
                departure_direction_deg=departure_deg,
                route_deviation=route_dev,
                ais_gap=ais_gap,
                raw_pings_count=cand_raw_count,
                sanitized_pings_count=cand_sanitized_count,
                rejected_pings_count=max(0, cand_raw_count - cand_sanitized_count),
            )
            results.append(features)

        # Sort candidates by proximity to source centroid
        results.sort(key=lambda f: f.closest_distance_km)
        return results
