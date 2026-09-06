from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any, Literal
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field, ConfigDict


class CoordinatePoint(BaseModel):
    """Geographic coordinate in WGS84 (EPSG:4326)."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")


class BoundingBox(BaseModel):
    """Spatial bounding box in WGS84."""
    min_latitude: float = Field(..., ge=-90.0, le=90.0)
    min_longitude: float = Field(..., ge=-180.0, le=180.0)
    max_latitude: float = Field(..., ge=-90.0, le=90.0)
    max_longitude: float = Field(..., ge=-180.0, le=180.0)


# =====================================================================
# 1. Satellite Observation
# =====================================================================

class SatelliteSensorType(str, Enum):
    SENTINEL_1A = "Sentinel-1A C-SAR"
    SENTINEL_1B = "Sentinel-1B C-SAR"
    RADARSAT_2 = "RADARSAT-2"
    TERRASAR_X = "TerraSAR-X"
    SYNTHETIC_SAR = "Synthetic/Demo SAR"


class SatelliteObservation(BaseModel):
    """Metadata and references for a SAR satellite scene acquisition."""
    image_id: str = Field(..., description="Unique product ID or granule identifier")
    timestamp: datetime = Field(..., description="UTC timestamp of satellite acquisition")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Center scene latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Center scene longitude")
    image_path: str = Field(..., description="Local file path, S3/cloud URI, or dataset key")
    sensor: str = Field(..., description="Sensor name (e.g. Sentinel-1A C-SAR)")
    resolution: float = Field(..., gt=0.0, description="Spatial resolution in meters per pixel")

    # Optional SAR-specific metadata
    polarization: Optional[List[str]] = Field(default_factory=lambda: ["VV", "VH"])
    orbit_direction: Optional[Literal["ASCENDING", "DESCENDING"]] = None
    incidence_angle_range: Optional[Tuple[float, float]] = None
    bounding_box: Optional[BoundingBox] = None
    extra_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


# =====================================================================
# 2. Spill Detection
# =====================================================================

class SpillGeometry(BaseModel):
    """GeoJSON-compatible geometry representation for detected slick polygon."""
    type: Literal["Polygon", "MultiPolygon"] = "Polygon"
    coordinates: List[Any] = Field(..., description="GeoJSON coordinates array in [lon, lat]")


class SpillDetection(BaseModel):
    """Oil slick detection and morphometric characterization output."""
    detected: bool = Field(..., description="True if an oil spill candidate was confirmed")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detector confidence score [0.0 - 1.0]")
    centroid: CoordinatePoint = Field(..., description="Weighted centroid of detected slick")
    bounding_box: BoundingBox = Field(..., description="Tight spatial envelope enclosing slick")
    area: float = Field(..., ge=0.0, description="Surface area of slick in square kilometers (km²)")
    perimeter: float = Field(..., ge=0.0, description="Perimeter length of slick in kilometers (km)")
    orientation: float = Field(..., ge=0.0, lt=360.0, description="Major axis orientation in degrees (0=North, clockwise)")
    spill_mask: SpillGeometry = Field(..., description="GeoJSON polygon or multipolygon defining boundary")

    # Look-alike discrimination & morphology features
    thickness_estimate: Optional[Literal["sheen", "rainbow", "metallic", "true_color", "dark_thick"]] = None
    estimated_volume_m3: Optional[float] = None
    look_alike_risk: Optional[Literal["low", "medium", "high"]] = Field(
        default="low", description="Risk of false positive from natural biogenic films, low-wind areas, or internal waves"
    )
    detector_algorithm: Optional[str] = Field(default="Adaptive-Threshold-U-Net")

    model_config = ConfigDict(extra="ignore")


# =====================================================================
# 3. Environmental State (Meteo-Oceanographic)
# =====================================================================

class EnvironmentalState(BaseModel):
    """
    Pointwise or spatio-temporally interpolated atmospheric and oceanic current vectors.
    
    Adheres to physical standards:
      - wind_u, wind_v: 10m wind velocity components in m/s (ERA5)
      - current_u, current_v: Surface ocean current velocity components in m/s (CMEMS)
      - wind_direction: Meteorological convention (direction FROM which wind blows, 0-360 deg)
      - current_direction: Oceanographic convention (direction TOWARDS which water sets, 0-360 deg)
      - quality_flags: Explicit status distinguishing exact, interpolated, and out-of-bounds data.
    """
    timestamp: datetime = Field(..., description="UTC timestamp of environmental state")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    location: Optional[CoordinatePoint] = None
    wind_u: Optional[float] = Field(None, description="10m Eastward wind component in m/s (ERA5 u10)")
    wind_v: Optional[float] = Field(None, description="10m Northward wind component in m/s (ERA5 v10)")
    current_u: Optional[float] = Field(None, description="Eastward surface ocean current velocity in m/s (CMEMS uo)")
    current_v: Optional[float] = Field(None, description="Northward surface ocean current velocity in m/s (CMEMS vo)")

    quality_flags: Dict[str, str] = Field(
        default_factory=lambda: {
            "wind": "EXACT_REANALYSIS_NODE",
            "current": "EXACT_REANALYSIS_NODE",
            "overall": "VALID",
        },
        description="Explicit provenance: EXACT_REANALYSIS_NODE, SPATIOTEMPORALLY_INTERPOLATED, DATA_UNAVAILABLE",
    )
    source: Dict[str, str] = Field(
        default_factory=lambda: {
            "wind": "ERA5 Reanalysis (ECMWF)",
            "current": "Copernicus Marine Global Ocean Physics",
        },
        description="Dataset provenance identification",
    )

    def model_post_init(self, __context) -> None:
        if self.location is None:
            self.location = CoordinatePoint(latitude=self.latitude, longitude=self.longitude)

    # Derived physical properties
    @property
    def wind_speed(self) -> float:
        if self.wind_u is None or self.wind_v is None:
            return 0.0
        return round(float((self.wind_u**2 + self.wind_v**2) ** 0.5), 2)

    @property
    def wind_speed_ms(self) -> float:
        """Alias for wind_speed."""
        return self.wind_speed

    @property
    def wind_direction(self) -> float:
        """
        Meteorological wind direction: Direction FROM which the wind blows (0-360 deg from True North).
        """
        if self.wind_u is None or self.wind_v is None:
            return 0.0
        import math
        deg = (math.atan2(-self.wind_u, -self.wind_v) * 180.0 / math.pi + 360.0) % 360.0
        return round(deg, 1)

    @property
    def current_speed(self) -> float:
        if self.current_u is None or self.current_v is None:
            return 0.0
        return round(float((self.current_u**2 + self.current_v**2) ** 0.5), 3)

    @property
    def current_speed_ms(self) -> float:
        """Alias for current_speed."""
        return self.current_speed

    @property
    def current_direction(self) -> float:
        """
        Oceanographic current direction: Direction TOWARDS which the water flows/sets (0-360 deg from True North).
        """
        if self.current_u is None or self.current_v is None:
            return 0.0
        import math
        deg = (math.atan2(self.current_u, self.current_v) * 180.0 / math.pi + 360.0) % 360.0
        return round(deg, 1)


class EnvironmentalGridSnapshot(BaseModel):
    """Spatio-temporal grid slice for numerical drift advection interpolation."""
    timestamp: datetime
    lats: List[float]
    lons: List[float]
    wind_u_grid: List[List[float]]
    wind_v_grid: List[List[float]]
    current_u_grid: List[List[float]]
    current_v_grid: List[List[float]]


# =====================================================================
# 4. AIS Point and Trajectory
# =====================================================================

class AISPoint(BaseModel):
    """Standardized single AIS position and kinematic report."""
    mmsi: str = Field(..., description="Maritime Mobile Service Identity (9-digit string)")
    timestamp: datetime = Field(..., description="UTC timestamp of ping")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    speed: float = Field(..., ge=0.0, description="Speed Over Ground (SOG) in knots")
    course: float = Field(..., ge=0.0, lt=360.0, description="Course Over Ground (COG) in degrees")
    heading: Optional[float] = Field(None, ge=0.0, lt=360.0, description="True Heading in degrees if available")

    # Optional vessel identification
    vessel_name: Optional[str] = None
    imo: Optional[str] = None
    callsign: Optional[str] = None
    vessel_type: Optional[str] = Field(None, description="e.g. Tanker, Cargo, Fishing, Passenger")
    navigational_status: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class AISTrajectory(BaseModel):
    """Reconstructed chronological trajectory of a vessel."""
    mmsi: str
    vessel_name: Optional[str] = None
    vessel_type: Optional[str] = None
    points: List[AISPoint] = Field(..., min_length=1)
    interpolated: bool = Field(default=False, description="True if missing pings were filled via kinematic interpolation")
    data_gaps_count: int = Field(default=0, description="Count of temporal gaps exceeding threshold (e.g. > 1 hour)")


class SpeedStatistics(BaseModel):
    """Kinematic speed statistics over the vessel trajectory and near source."""
    mean_speed_knots: float = Field(..., ge=0.0, description="Average Speed Over Ground (knots)")
    min_speed_knots: float = Field(..., ge=0.0, description="Minimum Speed Over Ground (knots)")
    max_speed_knots: float = Field(..., ge=0.0, description="Maximum Speed Over Ground (knots)")
    std_speed_knots: float = Field(..., ge=0.0, description="Standard deviation of speed (knots)")
    speed_at_cpa_knots: float = Field(..., ge=0.0, description="Speed Over Ground at Closest Point of Approach (knots)")
    speed_drop_knots: float = Field(default=0.0, description="Deceleration from transit speed to CPA speed (knots)")
    speed_drop_percent: float = Field(default=0.0, description="Percentage speed reduction at CPA compared to baseline")


class CourseStatistics(BaseModel):
    """Kinematic course statistics over the vessel trajectory."""
    mean_course_deg: float = Field(..., ge=0.0, lt=360.0, description="Mean course (degrees)")
    std_course_deg: float = Field(..., ge=0.0, description="Circular standard deviation of course (degrees)")
    min_course_deg: float = Field(..., ge=0.0, lt=360.0, description="Minimum course (degrees)")
    max_course_deg: float = Field(..., ge=0.0, lt=360.0, description="Maximum course (degrees)")
    max_course_change_deg: float = Field(default=0.0, description="Maximum course alteration between consecutive points (degrees)")


class RouteDeviation(BaseModel):
    """Indicator of route deviation, maneuvering, loitering, or sudden track changes."""
    detected: bool = Field(..., description="True if anomalous route deviation or loitering was detected")
    deviation_type: Optional[Literal["NONE", "SHARP_COURSE_CHANGE", "SPEED_DECELERATION", "LOITERING", "MANEUVERING"]] = "NONE"
    description: Optional[str] = Field(None, description="Human-readable description of deviation pattern")
    heading_change_deg: float = Field(default=0.0, description="Observed heading/course change near source")
    speed_reduction_ratio: float = Field(default=0.0, description="Fraction of speed reduced during encounter")


class AISGap(BaseModel):
    """Indicator of AIS transponder transmission gaps ('dark ship' behavior)."""
    detected: bool = Field(..., description="True if an uncharacteristic AIS silence was detected near release window")
    gap_duration_minutes: float = Field(default=0.0, description="Duration of longest gap in minutes")
    gap_start_time: Optional[datetime] = None
    gap_end_time: Optional[datetime] = None
    description: Optional[str] = None


class CandidateVesselFeatures(BaseModel):
    """
    Candidate vessel evidence features extracted from AIS trajectory analysis.
    
    IMPORTANT SCIENTIFIC PRINCIPLE:
    This model contains strictly objective kinematic and spatiotemporal evidence.
    It does NOT determine culpability or designate a vessel as responsible.
    """
    mmsi: str = Field(..., description="Maritime Mobile Service Identity (9-digit string)")
    vessel_name: Optional[str] = "Unknown"
    vessel_type: Optional[str] = "Unknown"
    imo: Optional[str] = None
    callsign: Optional[str] = None

    trajectory: AISTrajectory = Field(..., description="Reconstructed chronological trajectory")

    closest_point_to_source: CoordinatePoint = Field(
        ..., description="Vessel coordinates at Closest Point of Approach (CPA)"
    )
    closest_distance_km: float = Field(
        ..., ge=0.0, description="Minimum geodetic distance from vessel to source centroid (km)"
    )
    time_of_closest_approach: datetime = Field(
        ..., description="UTC timestamp of Closest Point of Approach (CPA)"
    )

    passed_through_source_region: bool = Field(
        ..., description="True if vessel trajectory entered the 95% KDE source polygon boundary"
    )
    time_spent_near_source_minutes: float = Field(
        ..., ge=0.0, description="Dwell time within the spatial search radius or source polygon in minutes"
    )
    entry_time: Optional[datetime] = Field(
        None, description="UTC timestamp when vessel first entered the spatial corridor"
    )
    exit_time: Optional[datetime] = Field(
        None, description="UTC timestamp when vessel exited the spatial corridor"
    )

    speed_statistics: SpeedStatistics = Field(..., description="Speed profile and deceleration metrics")
    course_statistics: CourseStatistics = Field(..., description="Course profile and maneuvering metrics")

    approach_direction_deg: float = Field(
        ..., ge=0.0, lt=360.0, description="Nautical direction (bearing) of vessel when approaching the source (0-360 deg)"
    )
    departure_direction_deg: float = Field(
        ..., ge=0.0, lt=360.0, description="Nautical direction (bearing) of vessel when departing from the source (0-360 deg)"
    )

    route_deviation: RouteDeviation = Field(..., description="Route alteration / maneuver / loiter indicator")
    ais_gap: AISGap = Field(default_factory=lambda: AISGap(detected=False), description="AIS silence / gap indicator")

    raw_pings_count: int = Field(default=0, description="Total pings received for vessel")
    sanitized_pings_count: int = Field(default=0, description="Valid pings retained after quality filtering")
    rejected_pings_count: int = Field(default=0, description="Pings rejected due to coordinates or impossible speeds")

    # Convenience aliases
    @property
    def closest_distance(self) -> float:
        return self.closest_distance_km

    @property
    def time_spent_near_source(self) -> float:
        return self.time_spent_near_source_minutes

    @property
    def route_deviation_detected(self) -> bool:
        return self.route_deviation.detected

    model_config = ConfigDict(extra="ignore")



# =====================================================================
# 5. Drift Result (Backward Hindcasting)
# =====================================================================

class ParticleStep(BaseModel):
    """Single particle state at a specific hindcast timestamp."""
    particle_id: int
    timestamp: datetime
    latitude: float
    longitude: float
    depth_m: float = 0.0


class ParticleTrajectory(BaseModel):
    """Chronological path of an individual Lagrangian particle moving backward in time."""
    particle_id: int
    steps: List[ParticleStep]


class DriftUncertainty(BaseModel):
    """Spatial and dispersion uncertainty envelope."""
    spatial_radius_km: float = Field(..., description="Effective 95% dispersion radius at release horizon in km")
    major_semi_axis_km: float = Field(..., description="Principal axis of dispersion ellipse")
    minor_semi_axis_km: float = Field(..., description="Minor axis of dispersion ellipse")
    diffusion_coefficient: float = Field(default=5.0, description="Horizontal eddy diffusivity Dh in m²/s")
    confidence_level: float = Field(default=0.95, description="Confidence interval of the bounding envelope")


class ReleaseTimeWindow(BaseModel):
    """Estimated oil release time bracket based on drift backwards and weathering."""
    earliest: datetime = Field(..., description="Earliest plausible spill release timestamp (UTC)")
    latest: datetime = Field(..., description="Latest plausible spill release timestamp (UTC)")
    most_probable: datetime = Field(..., description="Peak likelihood release timestamp (UTC)")
    slick_age_hours_range: Tuple[float, float] = Field(..., description="Estimated age range of slick in hours")


class DriftResult(BaseModel):
    """Output from the backward Lagrangian Monte Carlo hindcast engine."""
    particle_trajectories: List[ParticleTrajectory] = Field(
        ..., description="Ensemble of backward-advected particle paths"
    )
    source_region: SpillGeometry = Field(
        ..., description="GeoJSON polygon representing the 95% KDE credible source boundary"
    )
    source_region_50: Optional[SpillGeometry] = Field(
        None, description="GeoJSON polygon representing the 50% core credible source boundary"
    )
    source_region_90: Optional[SpillGeometry] = Field(
        None, description="GeoJSON polygon representing the 90% credible source boundary"
    )
    source_centroid: CoordinatePoint = Field(
        ..., description="Spatial center of mass of the probable source region"
    )
    uncertainty: DriftUncertainty = Field(
        ..., description="Dispersion metrics and uncertainty bounds"
    )
    release_time_window: ReleaseTimeWindow = Field(
        ..., description="Temporal interval during which the release likely occurred"
    )
    drift_duration_hours: float = Field(..., description="Total backward hindcast simulation hours")
    particle_count: int = Field(..., description="Total Monte Carlo particles simulated")
    forward_trajectories: Optional[List[ParticleTrajectory]] = Field(
        default_factory=list, description="Forward forecasted particle trajectories for future slick transport"
    )

    model_config = ConfigDict(extra="ignore")


# =====================================================================
# 6. Vessel Evidence & Attribution
# =====================================================================

class ClosestPointOfApproach(BaseModel):
    """Metrics of closest spatial-temporal encounter between vessel and hindcasted slick source."""
    distance_km: float = Field(..., ge=0.0, description="Minimum distance between vessel and source centroid")
    timestamp: datetime = Field(..., description="UTC timestamp of closest approach")
    vessel_latitude: float
    vessel_longitude: float
    source_latitude: float
    source_longitude: float


class EvidenceClassification(str, Enum):
    STRONG_CANDIDATE = "Strong Candidate"
    MODERATE_CANDIDATE = "Moderate Candidate"
    WEAK_CANDIDATE = "Weak Candidate"
    LOW_CONSISTENCY = "Low Consistency"
    HIGH_EVIDENCE = "High Evidence"
    MEDIUM_EVIDENCE = "Medium Evidence"
    LOW_EVIDENCE = "Low Evidence"
    INSUFFICIENT_EVIDENCE = "Insufficient Evidence"


class VesselEvidence(BaseModel):
    """
    Explainable attribution evidence card for an individual candidate vessel.
    
    IMPORTANT SCIENTIFIC PRINCIPLE:
    This is an 'Attribution Evidence Score' [0-100], NOT an uncalibrated probability of guilt.
    """
    mmsi: str = Field(..., description="Vessel MMSI")
    vessel_name: Optional[str] = "Unknown Vessel"
    vessel_type: Optional[str] = "Unknown"
    rank: int = Field(default=1, ge=1, description="Relative candidate rank based on evidence score")
    trajectory: Optional[AISTrajectory] = Field(None, description="Full chronological trajectory pings")

    # Component Scores (each normalized 0.0 - 100.0)
    spatial_score: float = Field(..., ge=0.0, le=100.0, description="Proximity to hindcast source region at release time")
    temporal_score: float = Field(..., ge=0.0, le=100.0, description="Alignment with release time window")
    trajectory_score: float = Field(..., ge=0.0, le=100.0, description="Intersection of vessel track with slick drift corridor")
    drift_score: float = Field(..., ge=0.0, le=100.0, description="Monte Carlo particle density intersection ratio")
    behavioral_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Anomaly score: AIS gaps, speed drops, maneuvers")
    component_scores: Dict[str, float] = Field(default_factory=dict, description="Dictionary of all component scores")

    # Aggregate Attribution Metric
    overall_evidence_score: float = Field(..., ge=0.0, le=100.0, description="Weighted composite Attribution Evidence Score")
    classification: EvidenceClassification = Field(..., description="Attribution category")

    # Explainability & Audit Trail
    explanation: List[str] = Field(
        ..., min_length=1, description="Structured natural-language justification bullet points for investigators"
    )
    counterfactual_explanation: Optional[str] = Field(
        None, description="Explains why score was penalized or what prevented a higher ranking"
    )
    limitations: List[str] = Field(
        default_factory=list, description="Scientific limitations, sensor uncertainties, and coverage caveats"
    )
    closest_approach: ClosestPointOfApproach = Field(
        ..., description="Details of closest point of approach in space and time"
    )
    ais_coverage_quality: Literal["continuous", "minor_gaps", "dark_period_suspected"] = Field(
        default="continuous", description="Integrity assessment of vessel's AIS transponder data"
    )
    scoring_weights_used: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class SensitivityPerturbation(BaseModel):
    """Systematic perturbation metric for sensitivity analysis."""
    parameter: str = Field(..., description="Perturbed physical parameter (e.g. wind speed, current direction)")
    perturbation: str = Field(..., description="Perturbation magnitude (e.g. +15%, -15 deg)")
    source_localization_error_km: float = Field(..., description="Centroid shift in km")
    release_time_error_hours: float = Field(..., description="Release window peak shift in hours")
    top1_accuracy_pct: float = Field(..., description="Attribution top-1 ranking consistency %")


class ValidationMetrics(BaseModel):
    """Scientific validation metrics across controlled synthetic scenarios."""
    benchmark_scenario_name: str = "Synthetic Controlled Ground-Truth Benchmark"
    source_localization_error_km: float = Field(..., description="Mean source localization error in km")
    release_time_error_hours: float = Field(..., description="Mean release time error in hours")
    top1_accuracy_pct: float = Field(..., description="Top-1 candidate identification accuracy %")
    top3_accuracy_pct: float = Field(..., description="Top-3 candidate identification accuracy %")
    scenarios_evaluated: int = Field(default=25, description="Count of evaluated Monte Carlo scenario runs")
    sensitivity_matrix: List[SensitivityPerturbation] = Field(default_factory=list)
    disclaimer: str = (
        "Prototype validation results from controlled/synthetic scenarios. "
        "Does not claim operational performance on uncalibrated real-world spills."
    )




# =====================================================================
# 7. Complete Investigation Aggregate
# =====================================================================

class InvestigationSummary(BaseModel):
    """Top-level investigation dossier combining observation, drift, and attribution."""
    investigation_id: str = Field(..., description="Unique investigation UUID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["pending", "processing", "completed", "failed"] = "completed"
    satellite_observation: SatelliteObservation
    spill_detection: SpillDetection
    environmental_snapshot: EnvironmentalState
    drift_result: DriftResult
    candidate_vessels: List[VesselEvidence] = Field(default_factory=list)
    top_candidate: Optional[VesselEvidence] = None
    insufficient_evidence_reason: Optional[str] = None
