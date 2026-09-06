import { ScenarioPreset } from './adapterInterface';
import { InvestigationSummary, ParticleTrajectory } from '../types/contracts';

// Helper to generate particle trajectories advected backward
function generateBackwardParticles(
  centerLat: number,
  centerLon: number,
  sourceLat: number,
  sourceLon: number,
  count: number,
  hours: number
): ParticleTrajectory[] {
  const particles: ParticleTrajectory[] = [];
  const baseTime = new Date('2026-08-14T06:15:00Z').getTime();

  for (let p = 0; p < count; p++) {
    const steps = [];
    const jitterLat = (Math.random() - 0.5) * 0.015;
    const jitterLon = (Math.random() - 0.5) * 0.015;

    for (let h = 0; h <= hours; h += 2) {
      const progress = h / hours;
      const lat = centerLat + (sourceLat - centerLat) * progress + jitterLat * progress * 1.8;
      const lon = centerLon + (sourceLon - centerLon) * progress + jitterLon * progress * 1.8;
      const t = new Date(baseTime - h * 3600 * 1000).toISOString();
      steps.push({
        particle_id: p,
        timestamp: t,
        latitude: Number(lat.toFixed(5)),
        longitude: Number(lon.toFixed(5)),
        depth_m: 0.0,
      });
    }
    particles.push({
      particle_id: p,
      steps,
    });
  }
  return particles;
}

// Helper to generate forward forecasted particle trajectories (+12 hours)
function generateForwardParticles(
  centerLat: number,
  centerLon: number,
  targetLat: number,
  targetLon: number,
  count: number,
  hours: number
): ParticleTrajectory[] {
  const particles: ParticleTrajectory[] = [];
  const baseTime = new Date('2026-08-14T06:15:00Z').getTime();

  for (let p = 0; p < count; p++) {
    const steps = [];
    const jitterLat = (Math.random() - 0.5) * 0.018;
    const jitterLon = (Math.random() - 0.5) * 0.018;

    for (let h = 0; h <= hours; h += 2) {
      const progress = h / hours;
      const lat = centerLat + (targetLat - centerLat) * progress + jitterLat * progress * 2.0;
      const lon = centerLon + (targetLon - centerLon) * progress + jitterLon * progress * 2.0;
      const t = new Date(baseTime + h * 3600 * 1000).toISOString();
      steps.push({
        particle_id: p + 200,
        timestamp: t,
        latitude: Number(lat.toFixed(5)),
        longitude: Number(lon.toFixed(5)),
        depth_m: 0.0,
      });
    }
    particles.push({
      particle_id: p + 200,
      steps,
    });
  }
  return particles;
}

// ----------------------------------------------------------------------
// SCENARIO 1: North Sea Tanker Discharge (High Evidence)
// ----------------------------------------------------------------------
const scenario1Particles = generateBackwardParticles(56.45, 3.20, 56.32, 3.01, 45, 18);
const scenario1ForwardParticles = generateForwardParticles(56.45, 3.20, 56.55, 3.35, 30, 12);


const scenario1Data: InvestigationSummary = {
  investigation_id: "INV-2026-NS-0814",
  created_at: "2026-08-14T07:30:00Z",
  status: "completed",
  satellite_observation: {
    image_id: "S1A_IW_GRDH_1SDV_20260814T061522_054321_066F12_B1A4",
    timestamp: "2026-08-14T06:15:22Z",
    latitude: 56.45,
    longitude: 3.20,
    image_path: "data/sample_sar/S1A_NORTH_SEA_20260814.tiff",
    sensor: "Sentinel-1A C-SAR",
    resolution: 10.0,
    polarization: ["VV", "VH"],
    orbit_direction: "DESCENDING",
    incidence_angle_range: [32.4, 38.1],
    bounding_box: {
      min_latitude: 56.35,
      min_longitude: 3.08,
      max_latitude: 56.55,
      max_longitude: 3.32,
    },
  },
  spill_detection: {
    detected: true,
    confidence: 0.94,
    centroid: { latitude: 56.452, longitude: 3.204 },
    bounding_box: {
      min_latitude: 56.431,
      min_longitude: 3.165,
      max_latitude: 56.473,
      max_longitude: 3.243,
    },
    area: 4.82,
    perimeter: 11.4,
    orientation: 248.5,
    spill_mask: {
      type: "Polygon",
      coordinates: [
        [
          [3.165, 56.435],
          [3.180, 56.442],
          [3.210, 56.460],
          [3.243, 56.473],
          [3.238, 56.468],
          [3.215, 56.452],
          [3.190, 56.439],
          [3.165, 56.435],
        ],
      ],
    },
    thickness_estimate: "dark_thick",
    estimated_volume_m3: 14.5,
    look_alike_risk: "low",
    detector_algorithm: "SAR-UNet-v2.1 (DeepLabv3+ Backbone)",
  },
  environmental_snapshot: {
    timestamp: "2026-08-14T06:00:00Z",
    latitude: 56.45,
    longitude: 3.20,
    wind_u: 6.2, // ~7.8 m/s from WSW
    wind_v: 4.8,
    current_u: 0.32, // ~0.35 m/s eastward
    current_v: 0.14,
  },
  drift_result: {
    particle_trajectories: scenario1Particles,
    source_region: {
      type: "Polygon",
      coordinates: [
        [
          [2.965, 56.305],
          [3.045, 56.312],
          [3.065, 56.340],
          [3.035, 56.355],
          [2.975, 56.345],
          [2.950, 56.322],
          [2.965, 56.305],
        ],
      ],
    },
    source_region_50: {
      type: "Polygon",
      coordinates: [
        [
          [2.985, 56.315],
          [3.030, 56.318],
          [3.045, 56.332],
          [3.025, 56.342],
          [2.990, 56.335],
          [2.975, 56.324],
          [2.985, 56.315],
        ],
      ],
    },
    source_region_90: {
      type: "Polygon",
      coordinates: [
        [
          [2.955, 56.300],
          [3.055, 56.308],
          [3.075, 56.342],
          [3.042, 56.360],
          [2.968, 56.348],
          [2.942, 56.320],
          [2.955, 56.300],
        ],
      ],
    },
    source_centroid: { latitude: 56.324, longitude: 3.018 },
    uncertainty: {
      spatial_radius_km: 2.85,
      major_semi_axis_km: 3.40,
      minor_semi_axis_km: 2.15,
      diffusion_coefficient: 5.0,
      confidence_level: 0.95,
    },
    release_time_window: {
      earliest: "2026-08-13T12:00:00Z",
      latest: "2026-08-13T16:30:00Z",
      most_probable: "2026-08-13T14:15:00Z",
      slick_age_hours_range: [13.75, 18.25],
    },
    drift_duration_hours: 18.0,
    particle_count: 45,
    forward_trajectories: scenario1ForwardParticles,
  },
  candidate_vessels: [
    {
      mmsi: "244123456",
      vessel_name: "MT Nordic Titan",
      vessel_type: "Crude Oil Tanker",
      rank: 1,
      spatial_score: 96.2,
      temporal_score: 94.0,
      trajectory_score: 92.5,
      drift_score: 89.0,
      behavioral_score: 85.0,
      overall_evidence_score: 92.1,
      classification: "Strong Candidate",
      explanation: [
        "Vessel track directly crossed the 95% Monte Carlo drift source envelope at 14:12 UTC (±3 min of peak hindcast window).",
        "Closest Point of Approach (CPA) was 0.42 km from the reconstructed source centroid.",
        "Observed significant speed reduction from 14.2 knots to 9.1 knots while transiting the source zone.",
        "Continuous AIS broadcast with zero transponder interruption confirmed.",
      ],
      counterfactual_explanation: "Candidate ranking is supported across all spatial, temporal, drift, and kinematic criteria; score was only slightly moderated by expected environmental dispersion bounds.",
      limitations: [
        "Attribution Evidence Score is a comparative forensic index, not an uncalibrated Bayesian probability.",
        "AIS broadcast interval is subject to transponder reporting frequency and satellite receiver latency.",
        "Hydrodynamic drift advection is constrained by ERA5 wind (31 km) and CMEMS current spatial resolution."
      ],
      component_scores: {
        spatial: 96.2,
        temporal: 94.0,
        trajectory: 92.5,
        drift: 89.0,
        behavioral: 85.0
      },
      trajectory: {
        mmsi: "244123456",
        vessel_name: "MT Nordic Titan",
        vessel_type: "Crude Oil Tanker",
        points: [
          { mmsi: "244123456", timestamp: "2026-08-13T10:00:00Z", latitude: 56.220, longitude: 2.870, speed: 14.5, course: 42.0 },
          { mmsi: "244123456", timestamp: "2026-08-13T12:00:00Z", latitude: 56.280, longitude: 2.950, speed: 14.2, course: 42.5 },
          { mmsi: "244123456", timestamp: "2026-08-13T13:00:00Z", latitude: 56.305, longitude: 2.985, speed: 13.8, course: 44.0 },
          { mmsi: "244123456", timestamp: "2026-08-13T14:12:00Z", latitude: 56.326, longitude: 3.021, speed: 9.1, course: 45.0 },
          { mmsi: "244123456", timestamp: "2026-08-13T15:30:00Z", latitude: 56.360, longitude: 3.070, speed: 14.0, course: 46.0 },
          { mmsi: "244123456", timestamp: "2026-08-13T17:00:00Z", latitude: 56.400, longitude: 3.130, speed: 14.3, course: 46.5 },
          { mmsi: "244123456", timestamp: "2026-08-13T19:00:00Z", latitude: 56.450, longitude: 3.210, speed: 14.1, course: 47.0 },
        ],
        interpolated: false,
        data_gaps_count: 0,
      },
      closest_approach: {
        distance_km: 0.42,
        timestamp: "2026-08-13T14:12:00Z",
        vessel_latitude: 56.326,
        vessel_longitude: 3.021,
        source_latitude: 56.324,
        source_longitude: 3.018,
      },
      ais_coverage_quality: "continuous",
      scoring_weights_used: {
        spatial: 0.25,
        temporal: 0.20,
        trajectory: 0.25,
        drift: 0.20,
        behavioral: 0.10,
      },
    },
    {
      mmsi: "311987654",
      vessel_name: "MV Pacific Trader",
      vessel_type: "Container Ship",
      rank: 2,
      spatial_score: 44.0,
      temporal_score: 51.2,
      trajectory_score: 38.0,
      drift_score: 42.0,
      behavioral_score: 30.0,
      overall_evidence_score: 41.5,
      classification: "Weak Candidate",
      explanation: [
        "Vessel passed 8.7 km north of the reconstructed source envelope.",
        "Temporal offset of 4.8 hours prior to earliest plausible release window.",
        "Maintained constant cruising speed of 18.5 knots on a standard shipping lane.",
      ],
      counterfactual_explanation: "Candidate ranking decreased because the vessel was 8.7 km north of the source centroid and arrived 4.8 hours prior to the estimated oil release window.",
      limitations: [
        "Attribution Evidence Score is a comparative forensic index, not an uncalibrated Bayesian probability."
      ],
      component_scores: {
        spatial: 44.0,
        temporal: 51.2,
        trajectory: 38.0,
        drift: 42.0,
        behavioral: 30.0
      },
      trajectory: {
        mmsi: "311987654",
        vessel_name: "MV Pacific Trader",
        vessel_type: "Container Ship",
        points: [
          { mmsi: "311987654", timestamp: "2026-08-13T08:00:00Z", latitude: 56.350, longitude: 2.920, speed: 18.4, course: 88.0 },
          { mmsi: "311987654", timestamp: "2026-08-13T09:00:00Z", latitude: 56.380, longitude: 2.980, speed: 18.5, course: 88.0 },
          { mmsi: "311987654", timestamp: "2026-08-13T09:40:00Z", latitude: 56.401, longitude: 3.030, speed: 18.6, course: 87.5 },
          { mmsi: "311987654", timestamp: "2026-08-13T10:30:00Z", latitude: 56.425, longitude: 3.110, speed: 18.4, course: 88.0 },
          { mmsi: "311987654", timestamp: "2026-08-13T12:00:00Z", latitude: 56.460, longitude: 3.250, speed: 18.5, course: 88.5 },
        ],
        interpolated: false,
        data_gaps_count: 0,
      },
      closest_approach: {
        distance_km: 8.70,
        timestamp: "2026-08-13T09:40:00Z",
        vessel_latitude: 56.401,
        vessel_longitude: 3.030,
        source_latitude: 56.324,
        source_longitude: 3.018,
      },
      ais_coverage_quality: "continuous",
    },
    {
      mmsi: "219654321",
      vessel_name: "FV Sea Hunter",
      vessel_type: "Fishing Vessel",
      rank: 3,
      spatial_score: 19.5,
      temporal_score: 22.0,
      trajectory_score: 15.0,
      drift_score: 14.5,
      behavioral_score: 20.0,
      overall_evidence_score: 18.2,
      classification: "Low Consistency",
      explanation: [
        "Operating 24.1 km south-east of source zone during relevant time window.",
        "Trawling behavior consistent with normal fishing activities; well outside 3σ dispersion envelope.",
      ],
      counterfactual_explanation: "Candidate ranking decreased because the vessel was 24.1 km south-east of the source zone and operated well outside the 3σ hydrodynamic dispersion envelope.",
      limitations: [
        "Attribution Evidence Score is a comparative forensic index, not an uncalibrated Bayesian probability."
      ],
      component_scores: {
        spatial: 19.5,
        temporal: 22.0,
        trajectory: 15.0,
        drift: 14.5,
        behavioral: 20.0
      },
      trajectory: {
        mmsi: "219654321",
        vessel_name: "FV Sea Hunter",
        vessel_type: "Fishing Vessel",
        points: [
          { mmsi: "219654321", timestamp: "2026-08-13T11:00:00Z", latitude: 56.100, longitude: 3.190, speed: 4.1, course: 155.0 },
          { mmsi: "219654321", timestamp: "2026-08-13T12:30:00Z", latitude: 56.120, longitude: 3.220, speed: 4.2, course: 160.0 },
          { mmsi: "219654321", timestamp: "2026-08-13T13:25:00Z", latitude: 56.135, longitude: 3.245, speed: 4.0, course: 165.0 },
          { mmsi: "219654321", timestamp: "2026-08-13T14:40:00Z", latitude: 56.150, longitude: 3.270, speed: 3.8, course: 170.0 },
          { mmsi: "219654321", timestamp: "2026-08-13T16:00:00Z", latitude: 56.165, longitude: 3.295, speed: 3.9, course: 168.0 },
        ],
        interpolated: false,
        data_gaps_count: 0,
      },
      closest_approach: {
        distance_km: 24.1,
        timestamp: "2026-08-13T13:25:00Z",
        vessel_latitude: 56.135,
        vessel_longitude: 3.245,
        source_latitude: 56.324,
        source_longitude: 3.018,
      },
      ais_coverage_quality: "continuous",
    },
  ],
  top_candidate: null,
  insufficient_evidence_reason: null,
};
scenario1Data.top_candidate = scenario1Data.candidate_vessels[0];


// ----------------------------------------------------------------------
// SCENARIO 2: Arabian Sea Dark Evasion (Medium Evidence with AIS Gap)
// ----------------------------------------------------------------------
const scenario2Particles = generateBackwardParticles(21.15, 68.30, 21.02, 68.10, 40, 14);

const scenario2Data: InvestigationSummary = {
  investigation_id: "INV-2026-AS-0902",
  created_at: "2026-09-02T11:45:00Z",
  status: "completed",
  satellite_observation: {
    image_id: "S1B_IW_GRDH_1SDV_20260902T093010_034112_041E20_C2B1",
    timestamp: "2026-09-02T09:30:10Z",
    latitude: 21.15,
    longitude: 68.30,
    image_path: "data/sample_sar/S1B_ARABIAN_SEA_20260902.tiff",
    sensor: "Sentinel-1B C-SAR",
    resolution: 10.0,
    polarization: ["VV", "VH"],
    orbit_direction: "ASCENDING",
    bounding_box: {
      min_latitude: 21.05,
      min_longitude: 68.15,
      max_latitude: 21.25,
      max_longitude: 68.45,
    },
  },
  spill_detection: {
    detected: true,
    confidence: 0.89,
    centroid: { latitude: 21.153, longitude: 68.302 },
    bounding_box: {
      min_latitude: 21.140,
      min_longitude: 21.275,
      max_latitude: 21.168,
      max_longitude: 68.328,
    },
    area: 2.15,
    perimeter: 7.2,
    orientation: 135.0,
    spill_mask: {
      type: "Polygon",
      coordinates: [
        [
          [68.280, 21.165],
          [68.310, 21.155],
          [68.328, 21.142],
          [68.318, 21.140],
          [68.295, 21.150],
          [68.280, 21.165],
        ],
      ],
    },
    thickness_estimate: "rainbow",
    estimated_volume_m3: 5.2,
    look_alike_risk: "low",
    detector_algorithm: "SAR-UNet-v2.1",
  },
  environmental_snapshot: {
    timestamp: "2026-09-02T09:00:00Z",
    latitude: 21.15,
    longitude: 68.30,
    wind_u: -4.5,
    wind_v: -3.2,
    current_u: 0.18,
    current_v: -0.12,
  },
  drift_result: {
    particle_trajectories: scenario2Particles,
    source_region: {
      type: "Polygon",
      coordinates: [
        [
          [68.075, 21.005],
          [68.130, 21.010],
          [68.140, 21.040],
          [68.115, 21.050],
          [68.065, 21.035],
          [68.075, 21.005],
        ],
      ],
    },
    source_centroid: { latitude: 21.025, longitude: 68.105 },
    uncertainty: {
      spatial_radius_km: 3.10,
      major_semi_axis_km: 3.80,
      minor_semi_axis_km: 2.40,
      diffusion_coefficient: 5.0,
      confidence_level: 0.95,
    },
    release_time_window: {
      earliest: "2026-09-01T21:00:00Z",
      latest: "2026-09-02T01:30:00Z",
      most_probable: "2026-09-01T23:15:00Z",
      slick_age_hours_range: [8.0, 12.5],
    },
    drift_duration_hours: 14.0,
    particle_count: 40,
  },
  candidate_vessels: [
    {
      mmsi: "636019888",
      vessel_name: "MT Gulf Vanguard",
      vessel_type: "Chemical/Oil Tanker",
      spatial_score: 72.0,
      temporal_score: 69.5,
      trajectory_score: 65.0,
      drift_score: 61.5,
      behavioral_score: 78.0,
      overall_evidence_score: 68.4,
      classification: "Medium Evidence",
      explanation: [
        "Vessel trajectory dead-reckoning places dead-center of source zone between 22:40 and 23:50 UTC.",
        "SUSPECTED AIS DARK PERIOD: Transponder broadcast went offline for 3 hours 25 minutes prior to entering the source envelope.",
        "Broadcast resumed 18 nautical miles downstream with a 4.2-knot speed discrepancy.",
        "Sufficient evidence for maritime authority inspection request, but lack of direct telemetry limits score to Medium Evidence.",
      ],
      closest_approach: {
        distance_km: 1.85,
        timestamp: "2026-09-01T23:20:00Z",
        vessel_latitude: 21.038,
        vessel_longitude: 68.112,
        source_latitude: 21.025,
        source_longitude: 68.105,
      },
      ais_coverage_quality: "dark_period_suspected",
    },
  ],
  top_candidate: null,
  insufficient_evidence_reason: null,
};
scenario2Data.top_candidate = scenario2Data.candidate_vessels[0];

// ----------------------------------------------------------------------
// SCENARIO 3: Strait of Malacca Dispersed Slick (Insufficient Evidence State)
// ----------------------------------------------------------------------
const scenario3Particles = generateBackwardParticles(2.75, 101.90, 2.60, 101.72, 35, 24);

const scenario3Data: InvestigationSummary = {
  investigation_id: "INV-2026-SM-0828",
  created_at: "2026-08-28T16:20:00Z",
  status: "completed",
  satellite_observation: {
    image_id: "S1A_IW_GRDH_1SDV_20260828T140510_049811_05EC10_A45B",
    timestamp: "2026-08-28T14:05:10Z",
    latitude: 2.75,
    longitude: 101.90,
    image_path: "data/sample_sar/S1A_MALACCA_20260828.tiff",
    sensor: "Sentinel-1A C-SAR",
    resolution: 10.0,
    bounding_box: {
      min_latitude: 2.65,
      min_longitude: 101.75,
      max_latitude: 2.85,
      max_longitude: 102.05,
    },
  },
  spill_detection: {
    detected: true,
    confidence: 0.72,
    centroid: { latitude: 2.752, longitude: 101.904 },
    bounding_box: {
      min_latitude: 2.740,
      min_longitude: 101.888,
      max_latitude: 2.765,
      max_longitude: 101.920,
    },
    area: 1.15,
    perimeter: 4.8,
    orientation: 310.0,
    spill_mask: {
      type: "Polygon",
      coordinates: [
        [
          [101.890, 2.742],
          [101.915, 2.758],
          [101.920, 2.765],
          [101.905, 2.752],
          [101.890, 2.742],
        ],
      ],
    },
    thickness_estimate: "sheen",
    estimated_volume_m3: 1.1,
    look_alike_risk: "medium",
    detector_algorithm: "SAR-UNet-v2.1",
  },
  environmental_snapshot: {
    timestamp: "2026-08-28T14:00:00Z",
    latitude: 2.75,
    longitude: 101.90,
    wind_u: 2.1,
    wind_v: 1.5,
    current_u: 0.45,
    current_v: 0.30,
  },
  drift_result: {
    particle_trajectories: scenario3Particles,
    source_region: {
      type: "Polygon",
      coordinates: [
        [
          [101.695, 2.585],
          [101.745, 2.592],
          [101.755, 2.620],
          [101.715, 2.625],
          [101.685, 2.605],
          [101.695, 2.585],
        ],
      ],
    },
    source_centroid: { latitude: 2.605, longitude: 101.722 },
    uncertainty: {
      spatial_radius_km: 4.50,
      major_semi_axis_km: 5.20,
      minor_semi_axis_km: 3.80,
      diffusion_coefficient: 5.0,
      confidence_level: 0.95,
    },
    release_time_window: {
      earliest: "2026-08-27T14:00:00Z",
      latest: "2026-08-27T22:00:00Z",
      most_probable: "2026-08-27T18:00:00Z",
      slick_age_hours_range: [16.0, 24.0],
    },
    drift_duration_hours: 24.0,
    particle_count: 35,
  },
  candidate_vessels: [
    {
      mmsi: "538004123",
      vessel_name: "MV Oriental Fortune",
      vessel_type: "Bulk Carrier",
      spatial_score: 38.0,
      temporal_score: 41.0,
      trajectory_score: 35.0,
      drift_score: 32.0,
      behavioral_score: 30.0,
      overall_evidence_score: 36.8,
      classification: "Insufficient Evidence",
      explanation: [
        "Vessel passed 14.8 km east of the 95% source boundary (> 3.3σ dispersion radius).",
        "Temporal offset of 7.8 hours from the calculated release-time window.",
        "Evidence score (36.8) falls below scientific attribution threshold (50.0).",
      ],
      closest_approach: {
        distance_km: 14.8,
        timestamp: "2026-08-28T01:45:00Z",
        vessel_latitude: 2.650,
        vessel_longitude: 101.850,
        source_latitude: 2.605,
        source_longitude: 101.722,
      },
      ais_coverage_quality: "continuous",
    },
    {
      mmsi: "477123987",
      vessel_name: "MT Straits Glory",
      vessel_type: "Oil Products Tanker",
      spatial_score: 31.5,
      temporal_score: 34.0,
      trajectory_score: 28.0,
      drift_score: 25.0,
      behavioral_score: 25.0,
      overall_evidence_score: 29.8,
      classification: "Insufficient Evidence",
      explanation: [
        "Transited eastbound lane 19.2 km away from hindcasted release centroid.",
        "Timing inconsistent with estimated slick age and surface weathering kinetics.",
      ],
      closest_approach: {
        distance_km: 19.2,
        timestamp: "2026-08-27T10:15:00Z",
        vessel_latitude: 2.510,
        vessel_longitude: 101.860,
        source_latitude: 2.605,
        source_longitude: 101.722,
      },
      ais_coverage_quality: "continuous",
    },
  ],
  top_candidate: null, // Zero attributed candidate
  insufficient_evidence_reason:
    "No candidate vessel met the minimum Attribution Evidence Threshold of 50.0. All candidate vessels in the corridor either transited outside the 95% Monte Carlo drift dispersion envelope (> 3σ) or possessed timing discrepancies exceeding 7.5 hours. Scientific attribution is strictly withheld due to insufficient corroborating evidence.",
};

// ----------------------------------------------------------------------
// PRESET CATALOG
// ----------------------------------------------------------------------
export const PRESET_SCENARIOS: ScenarioPreset[] = [
  {
    id: "scenario-1",
    name: "North Sea Crude Discharge",
    region: "North Sea (Norway/UK Sector)",
    sensor: "Sentinel-1A C-SAR",
    summary: "Large elongated slick. Tanker MT Nordic Titan directly bisects backward drift cloud during peak release window.",
    expectedOutcome: "High Evidence",
    data: scenario1Data,
  },
  {
    id: "scenario-2",
    name: "Arabian Sea Dark Ship Incident",
    region: "Arabian Sea (Gujarat Offshore)",
    sensor: "Sentinel-1B C-SAR",
    summary: "Moderate slick. Chemical tanker transited with 3.5-hour AIS dark transponder shutdown.",
    expectedOutcome: "Medium Evidence",
    data: scenario2Data,
  },
  {
    id: "scenario-3",
    name: "Strait of Malacca Weathered Slick",
    region: "Strait of Malacca (Port Dickson)",
    sensor: "Sentinel-1A C-SAR",
    summary: "Weathered sheen with multiple transiting vessels. No candidate meets spatial-temporal threshold.",
    expectedOutcome: "Insufficient Evidence",
    data: scenario3Data,
  },
];
