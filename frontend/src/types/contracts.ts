/**
 * SIH 2026 - Problem Statement 26143
 * TypeScript Data Contracts for Frontend (React + MapLibre / Leaflet)
 * 1-to-1 parity with Backend Pydantic Domain Models
 */

export interface CoordinatePoint {
  latitude: number;
  longitude: number;
}

export interface BoundingBox {
  min_latitude: number;
  min_longitude: number;
  max_latitude: number;
  max_longitude: number;
}

// ----------------------------------------------------------------------
// 1. Satellite Observation
// ----------------------------------------------------------------------

export type SatelliteSensorType =
  | 'Sentinel-1A C-SAR'
  | 'Sentinel-1B C-SAR'
  | 'RADARSAT-2'
  | 'TerraSAR-X'
  | 'Synthetic/Demo SAR';

export interface SatelliteObservation {
  image_id: string;
  timestamp: string; // ISO-8601 UTC
  latitude: number;
  longitude: number;
  image_path: string;
  sensor: string;
  resolution: number; // meters per pixel
  polarization?: string[];
  orbit_direction?: 'ASCENDING' | 'DESCENDING';
  incidence_angle_range?: [number, number];
  bounding_box?: BoundingBox;
  extra_metadata?: Record<string, unknown>;
}

// ----------------------------------------------------------------------
// 2. Spill Detection
// ----------------------------------------------------------------------

export interface SpillGeometry {
  type: 'Polygon' | 'MultiPolygon';
  coordinates: number[][][] | number[][][][]; // GeoJSON format: [lon, lat]
}

export interface SpillDetection {
  detected: boolean;
  confidence: number; // 0.0 - 1.0
  centroid: CoordinatePoint;
  bounding_box: BoundingBox;
  area: number; // km²
  perimeter: number; // km
  orientation: number; // degrees (0-360)
  spill_mask: SpillGeometry;
  thickness_estimate?: 'sheen' | 'rainbow' | 'metallic' | 'true_color' | 'dark_thick';
  estimated_volume_m3?: number;
  look_alike_risk?: 'low' | 'medium' | 'high';
  detector_algorithm?: string;
}

// ----------------------------------------------------------------------
// 3. Environmental State
// ----------------------------------------------------------------------

export interface EnvironmentalState {
  timestamp: string; // ISO-8601 UTC
  latitude: number;
  longitude: number;
  wind_u: number; // m/s (ERA5 u10)
  wind_v: number; // m/s (ERA5 v10)
  current_u: number; // m/s (CMEMS)
  current_v: number; // m/s (CMEMS)
  wind_speed?: number; // m/s
  wind_direction?: number; // degrees FROM north (meteorological)
  current_speed?: number; // m/s
  current_direction?: number; // degrees TOWARDS north (oceanographic)
  quality_flags?: Record<string, string>;
  source?: Record<string, string>;
  units?: Record<string, string>;
}

// ----------------------------------------------------------------------
// 4. AIS Point and Trajectory
// ----------------------------------------------------------------------

export interface AISPoint {
  mmsi: string;
  timestamp: string; // ISO-8601 UTC
  latitude: number;
  longitude: number;
  speed: number; // knots
  course: number; // degrees (0-360)
  heading?: number | null; // degrees (0-360)
  vessel_name?: string;
  imo?: string;
  callsign?: string;
  vessel_type?: string;
  navigational_status?: string;
}

export interface AISTrajectory {
  mmsi: string;
  vessel_name?: string;
  vessel_type?: string;
  points: AISPoint[];
  interpolated: boolean;
  data_gaps_count: number;
}

export interface SpeedStatistics {
  mean_speed_knots: number;
  min_speed_knots: number;
  max_speed_knots: number;
  std_speed_knots: number;
  speed_at_cpa_knots: number;
  speed_drop_knots: number;
  speed_drop_percent: number;
}

export interface CourseStatistics {
  mean_course_deg: number;
  std_course_deg: number;
  min_course_deg: number;
  max_course_deg: number;
  max_course_change_deg: number;
}

export interface RouteDeviation {
  detected: boolean;
  deviation_type?: 'NONE' | 'SHARP_COURSE_CHANGE' | 'SPEED_DECELERATION' | 'LOITERING' | 'MANEUVERING';
  description?: string;
  heading_change_deg: number;
  speed_reduction_ratio: number;
}

export interface AISGap {
  detected: boolean;
  gap_duration_minutes: number;
  gap_start_time?: string | null;
  gap_end_time?: string | null;
  description?: string | null;
}

export interface CandidateVesselFeatures {
  mmsi: string;
  vessel_name?: string;
  vessel_type?: string;
  imo?: string | null;
  callsign?: string | null;
  trajectory: AISTrajectory;
  closest_point_to_source: CoordinatePoint;
  closest_distance_km: number;
  min_distance_km?: number;
  time_of_closest_approach: string;
  passed_through_source_region: boolean;
  entered_source_region?: boolean;
  time_spent_near_source_minutes: number;
  entry_time?: string | null;
  exit_time?: string | null;
  speed_statistics: SpeedStatistics;
  course_statistics: CourseStatistics;
  approach_direction_deg: number;
  departure_direction_deg: number;
  route_deviation: RouteDeviation;
  ais_gap: AISGap;
  ais_gap_detected?: boolean;
  temporal_match?: boolean;
  spatial_match?: boolean;
  trajectory_quality?: string;
  candidate_status?: string;
  raw_pings_count?: number;
  sanitized_pings_count?: number;
  rejected_pings_count?: number;
}

export interface AISCandidateRequest {
  probable_source_region?: SpillGeometry | null;
  source_centroid?: CoordinatePoint | null;
  release_time_window: ReleaseTimeWindow;
  spatial_radius_km?: number;
  ais_dataset_path?: string | null;
  raw_pings?: Record<string, any>[] | null;
  temporal_tolerance_hours?: number;
  app_mode?: string | null;
}

// ----------------------------------------------------------------------
// 5. Drift Result
// ----------------------------------------------------------------------

export interface ParticleStep {
  particle_id: number;
  timestamp: string; // ISO-8601 UTC
  latitude: number;
  longitude: number;
  depth_m: number;
}

export interface ParticleTrajectory {
  particle_id: number;
  steps: ParticleStep[];
}

export interface DriftUncertainty {
  spatial_radius_km: number;
  major_semi_axis_km: number;
  minor_semi_axis_km: number;
  diffusion_coefficient: number;
  confidence_level: number;
}

export interface ReleaseTimeWindow {
  earliest: string; // ISO-8601 UTC
  latest: string; // ISO-8601 UTC
  most_probable: string; // ISO-8601 UTC
  slick_age_hours_range: [number, number];
}

export interface DriftResult {
  particle_trajectories: ParticleTrajectory[];
  source_region: SpillGeometry; // 95% KDE GeoJSON polygon
  source_region_50?: SpillGeometry; // 50% core credible zone
  source_region_90?: SpillGeometry; // 90% credible zone
  source_centroid: CoordinatePoint;
  uncertainty: DriftUncertainty;
  release_time_window: ReleaseTimeWindow;
  drift_duration_hours: number;
  particle_count: number;
  forward_trajectories?: ParticleTrajectory[];
}

// ----------------------------------------------------------------------
// 6. Vessel Evidence & Attribution
// ----------------------------------------------------------------------

export interface ClosestPointOfApproach {
  distance_km: number;
  timestamp: string; // ISO-8601 UTC
  vessel_latitude: number;
  vessel_longitude: number;
  source_latitude: number;
  source_longitude: number;
}

export type EvidenceClassification =
  | 'Strong Candidate'
  | 'Moderate Candidate'
  | 'Weak Candidate'
  | 'Low Consistency'
  | 'High Evidence'
  | 'Medium Evidence'
  | 'Low Evidence'
  | 'Insufficient Evidence';

export interface VesselEvidence {
  mmsi: string;
  vessel_name?: string;
  vessel_type?: string;
  rank?: number;
  trajectory?: AISTrajectory;

  // Component Scores (0 - 100)
  spatial_score: number;
  temporal_score: number;
  trajectory_score: number;
  drift_score: number;
  behavioral_score?: number | null;
  component_scores?: Record<string, number>;

  // Aggregate Attribution Metric (Attribution Evidence Score)
  overall_evidence_score: number;
  classification: EvidenceClassification;

  // Explainability & Audit Trail
  explanation: string[];
  counterfactual_explanation?: string;
  limitations?: string[];
  closest_approach: ClosestPointOfApproach;
  ais_coverage_quality: 'continuous' | 'minor_gaps' | 'dark_period_suspected';
  scoring_weights_used?: Record<string, number>;
  candidate_features?: CandidateVesselFeatures;
}

export interface SensitivityPerturbation {
  parameter: string;
  perturbation: string;
  source_localization_error_km: number;
  release_time_error_hours: number;
  top1_accuracy_pct: number;
}

export interface ValidationMetrics {
  benchmark_scenario_name: string;
  source_localization_error_km: number;
  release_time_error_hours: number;
  top1_accuracy_pct: number;
  top3_accuracy_pct: number;
  scenarios_evaluated: number;
  sensitivity_matrix: SensitivityPerturbation[];
  disclaimer: string;
}


// ----------------------------------------------------------------------
// 7. Complete Investigation Dossier
// ----------------------------------------------------------------------

export interface InvestigationSummary {
  investigation_id: string;
  created_at: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  satellite_observation: SatelliteObservation;
  spill_detection: SpillDetection;
  environmental_snapshot: EnvironmentalState;
  drift_result: DriftResult;
  candidate_vessels: VesselEvidence[];
  top_candidate?: VesselEvidence | null;
  insufficient_evidence_reason?: string | null;
}
