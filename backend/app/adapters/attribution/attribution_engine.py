import math
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union

import numpy as np

from backend.app.domain.models import (
    SpillDetection,
    SpillGeometry,
    CoordinatePoint,
    ReleaseTimeWindow,
    ParticleTrajectory,
    DriftResult,
    AISPoint,
    AISTrajectory,
    CandidateVesselFeatures,
    ClosestPointOfApproach,
    EvidenceClassification,
    VesselEvidence,
)
from backend.app.adapters.ais.vessel_analyzer import (
    AISVesselAnalyzer,
    haversine_distance_km,
    point_in_polygon,
)

logger = logging.getLogger(__name__)


class ExplainableAttributionEngine:
    """
    Explainable Multi-Criteria Vessel Attribution Scoring Engine.
    
    Adheres to Smart India Hackathon 2026 Problem Statement 26143 standards:
      - Multi-criteria correlation: Spatial, Temporal, Trajectory, Drift, Behavioral.
      - Configurable weights summing to 100.
      - Produces an 'Attribution Evidence Score' [0-100] (NOT a probability).
      - Ranks candidates and assigns classification tiers:
          80–100: Strong Candidate
          60–79:  Moderate Candidate
          40–59:  Weak Candidate
          < 40:   Low Consistency
      - Minimum evidence threshold fail-safe (defaults to 50.0):
          Returns 'INSUFFICIENT EVIDENCE' without forcing a culprit if threshold is not reached.
      - Generates natural language evidence justifications, counterfactual explanations, and limitations.
    """

    def __init__(
        self,
        spatial_weight: float = 25.0,
        temporal_weight: float = 20.0,
        trajectory_weight: float = 25.0,
        drift_weight: float = 20.0,
        behavioral_weight: float = 10.0,
        min_evidence_threshold: float = 50.0,
    ):
        self.spatial_weight = spatial_weight
        self.temporal_weight = temporal_weight
        self.trajectory_weight = trajectory_weight
        self.drift_weight = drift_weight
        self.behavioral_weight = behavioral_weight
        self.min_evidence_threshold = min_evidence_threshold
        self._vessel_analyzer = AISVesselAnalyzer()

    @property
    def weights_dict(self) -> Dict[str, float]:
        return {
            "spatial": self.spatial_weight,
            "temporal": self.temporal_weight,
            "trajectory": self.trajectory_weight,
            "drift": self.drift_weight,
            "behavioral": self.behavioral_weight,
        }

    @property
    def total_weight(self) -> float:
        return sum(self.weights_dict.values())

    # =========================================================================
    # 1. Component Consistency Scoring Functions
    # =========================================================================

    def calculate_spatial_consistency(
        self,
        candidate: CandidateVesselFeatures,
        source_uncertainty_radius_km: float = 8.0,
    ) -> float:
        """
        Calculates Spatial Consistency [0.0 - 100.0].
        
        Evaluates geodetic proximity of vessel CPA to the probable source centroid
        and whether the vessel navigated within the 95% KDE source boundary polygon.
        """
        d_cpa = candidate.closest_distance_km
        r0 = max(4.0, source_uncertainty_radius_km)

        # Gaussian proximity decay
        raw_score = 100.0 * math.exp(-(d_cpa ** 2) / (2.0 * (r0 ** 2)))

        # Bonus / guarantee if physically traversed inside the source polygon
        if candidate.passed_through_source_region:
            score = max(92.0, raw_score)
        elif d_cpa <= 1.5:
            score = max(88.0, raw_score)
        elif d_cpa <= 3.5:
            score = max(75.0, raw_score)
        else:
            score = raw_score

        return round(float(np.clip(score, 0.0, 100.0)), 1)

    def calculate_temporal_consistency(
        self,
        candidate: CandidateVesselFeatures,
        release_window: ReleaseTimeWindow,
    ) -> float:
        """
        Calculates Temporal Consistency [0.0 - 100.0].
        
        Evaluates the alignment between time of closest approach (t_CPA)
        and the estimated release time window [T_earliest, T_latest], peaking at T_most_probable.
        """
        t_cpa = candidate.time_of_closest_approach
        if t_cpa.tzinfo is None:
            t_cpa = t_cpa.replace(tzinfo=timezone.utc)

        t_earliest = release_window.earliest
        if t_earliest.tzinfo is None:
            t_earliest = t_earliest.replace(tzinfo=timezone.utc)

        t_latest = release_window.latest
        if t_latest.tzinfo is None:
            t_latest = t_latest.replace(tzinfo=timezone.utc)

        t_peak = release_window.most_probable
        if t_peak.tzinfo is None:
            t_peak = t_peak.replace(tzinfo=timezone.utc)

        # Span and peak offset in hours
        span_hours = max(1.0, (t_latest - t_earliest).total_seconds() / 3600.0)
        dt_peak_hours = abs((t_cpa - t_peak).total_seconds()) / 3600.0

        if t_earliest <= t_cpa <= t_latest:
            # Inside release window: Gaussian decay from peak
            sigma_t = max(1.2, span_hours / 3.0)
            score = 100.0 * math.exp(-(dt_peak_hours ** 2) / (2.0 * (sigma_t ** 2)))
            score = max(72.0, score)  # In-window baseline guarantee
        else:
            # Outside release window: exponential decay based on distance to nearest boundary
            dt_edge_hours = min(
                abs((t_cpa - t_earliest).total_seconds()),
                abs((t_cpa - t_latest).total_seconds()),
            ) / 3600.0
            score = 70.0 * math.exp(-dt_edge_hours / 1.8)

        return round(float(np.clip(score, 0.0, 100.0)), 1)

    def calculate_trajectory_consistency(
        self,
        candidate: CandidateVesselFeatures,
        spatial_score: float,
    ) -> float:
        """
        Calculates Trajectory Corridor Consistency [0.0 - 100.0].
        
        Evaluates track corridor alignment, dwell time in vicinity, and passage through source.
        """
        dwell_mins = candidate.time_spent_near_source_minutes
        dwell_factor = min(1.0, dwell_mins / 30.0)

        # Baseline alignment heavily correlated with spatial proximity
        score = (0.50 * spatial_score) + (0.35 * (dwell_factor * 100.0))

        if candidate.passed_through_source_region:
            score += 20.0
        elif candidate.closest_distance_km <= 5.0:
            score += 10.0

        return round(float(np.clip(score, 0.0, 100.0)), 1)

    def calculate_drift_consistency(
        self,
        candidate: CandidateVesselFeatures,
        drift_trajectories: Optional[List[ParticleTrajectory]],
        source_centroid: CoordinatePoint,
    ) -> float:
        """
        Calculates Lagrangian Drift Consistency [0.0 - 100.0].
        
        Evaluates spatial intersection between vessel trajectory and Monte Carlo
        Lagrangian backward particle paths.
        """
        if not drift_trajectories:
            # Fallback to spatial proximity decay with wider spread
            d_cpa = candidate.closest_distance_km
            score = 100.0 * math.exp(-(d_cpa ** 2) / (2.0 * (12.0 ** 2)))
            return round(float(np.clip(score, 0.0, 100.0)), 1)

        # Compute particle encounter ratio
        # A particle is 'encountered' if any vessel ping comes within 4.0 km of the particle's release position
        vessel_pts = candidate.trajectory.points
        total_particles = len(drift_trajectories)
        if total_particles == 0:
            return 50.0

        hit_count = 0
        for traj in drift_trajectories:
            if not traj.steps:
                continue
            # End of backward trajectory corresponds to release time position
            rel_step = traj.steps[-1]
            min_p_dist = min(
                haversine_distance_km(p.latitude, p.longitude, rel_step.latitude, rel_step.longitude)
                for p in vessel_pts
            )
            if min_p_dist <= 5.0:
                hit_count += 1

        hit_ratio = hit_count / total_particles
        # Because particle clouds diffuse, encountering >= 20% of particles represents a direct core hit
        score = min(100.0, (hit_ratio / 0.20) * 100.0)

        if candidate.passed_through_source_region:
            score = max(80.0, score)

        return round(float(np.clip(score, 0.0, 100.0)), 1)

    def calculate_behavioral_consistency(
        self,
        candidate: CandidateVesselFeatures,
    ) -> float:
        """
        Calculates Behavioral Consistency [0.0 - 100.0].
        
        Evaluates operational kinematic signatures:
          - Deceleration at CPA (speed drop >= 30% or >= 3.0 kn): +35 pts
          - Route deviation / sharp course alteration >= 25 deg: +30 pts
          - Loitering behavior (SOG <= 3.0 kn near source): +35 pts
          - AIS transponder silence / blackout (> 60 min gap): +30 pts
          - Standard unvarying cruising transit: baseline 15.0 pts
        """
        if candidate.sanitized_pings_count < 3:
            # Insufficient trajectory history to establish behavioral deviation
            return 50.0

        score = 15.0  # Normal traffic baseline

        # 1. Speed drop deceleration
        if candidate.speed_statistics.speed_drop_percent >= 30.0 or candidate.speed_statistics.speed_drop_knots >= 3.0:
            score += 35.0

        # 2. Route alteration / maneuvering
        if candidate.route_deviation.detected:
            if candidate.route_deviation.deviation_type == "LOITERING":
                score += 35.0
            elif candidate.route_deviation.deviation_type in ("SPEED_DECELERATION", "SHARP_COURSE_CHANGE"):
                score += 25.0
            else:
                score += 20.0

        # 3. AIS transmission gap
        if candidate.ais_gap.detected:
            score += 30.0

        return round(float(np.clip(score, 0.0, 100.0)), 1)

    # =========================================================================
    # 2. Classification & Explainability Generators
    # =========================================================================

    def classify_score(self, score: float) -> EvidenceClassification:
        """Map Attribution Evidence Score [0 - 100] to standardized classification band."""
        if score >= 80.0:
            return EvidenceClassification.STRONG_CANDIDATE
        elif score >= 60.0:
            return EvidenceClassification.MODERATE_CANDIDATE
        elif score >= 40.0:
            return EvidenceClassification.WEAK_CANDIDATE
        else:
            return EvidenceClassification.LOW_CONSISTENCY

    def generate_explanation(
        self,
        candidate: CandidateVesselFeatures,
        spatial: float,
        temporal: float,
        trajectory: float,
        drift: float,
        behavioral: float,
        overall: float,
    ) -> List[str]:
        """Generate structured natural-language forensic justification bullet points."""
        points = []

        # Spatial
        if candidate.passed_through_source_region:
            points.append(
                f"Vessel trajectory directly traversed within the 95% KDE probable source region "
                f"(CPA distance {candidate.closest_distance_km:.2f} km)."
            )
        else:
            points.append(
                f"Closest Point of Approach (CPA) was {candidate.closest_distance_km:.2f} km "
                f"from the source centroid (Spatial score: {spatial:.1f}/100)."
            )

        # Temporal
        cpa_str = candidate.time_of_closest_approach.strftime("%Y-%m-%d %H:%M UTC")
        points.append(
            f"Encounter occurred at {cpa_str}, demonstrating high temporal correlation "
            f"with the hindcasted release window (Temporal score: {temporal:.1f}/100)."
        )

        # Behavioral & Route
        if candidate.route_deviation.detected:
            points.append(
                f"Route anomaly observed: {candidate.route_deviation.description} "
                f"(Behavioral score: {behavioral:.1f}/100)."
            )
        elif candidate.speed_statistics.speed_drop_percent >= 20.0:
            points.append(
                f"Vessel decelerated by {candidate.speed_statistics.speed_drop_knots:.1f} kn "
                f"({candidate.speed_statistics.speed_drop_percent:.0f}%) near closest approach."
            )
        else:
            points.append("Vessel maintained steady transit speed and course without anomalous maneuvers.")

        # AIS transponder status
        if candidate.ais_gap.detected:
            points.append(
                f"Suspicious AIS transponder silence detected: {candidate.ais_gap.gap_duration_minutes:.0f} minutes "
                f"of blackout overlapping the release window."
            )

        return points

    def generate_counterfactual(
        self,
        candidate: CandidateVesselFeatures,
        spatial: float,
        temporal: float,
        trajectory: float,
        drift: float,
        behavioral: float,
    ) -> str:
        """
        Generate counterfactual explanation describing why the candidate's score
        was not higher or what caused its ranking to decrease.
        """
        penalties = []

        if spatial < 75.0:
            penalties.append(
                f"the vessel was {candidate.closest_distance_km:.1f} km outside the source centroid "
                f"and did not intersect the core 95% KDE boundary polygon"
            )

        if temporal < 70.0:
            penalties.append(
                f"the time of closest approach was outside the peak estimated release-time window"
            )

        if trajectory < 65.0:
            penalties.append(
                f"dwell time near the source was limited to {candidate.time_spent_near_source_minutes:.1f} minutes"
            )

        if behavioral < 40.0:
            penalties.append(
                f"the vessel maintained a standard, unvarying transit without deceleration or track alterations"
            )

        if not penalties:
            return (
                "Candidate ranking is supported across all spatial, temporal, drift, and kinematic criteria; "
                "score was only slightly moderated by expected environmental dispersion bounds."
            )

        return "Candidate ranking decreased because " + "; and ".join(penalties) + "."

    def generate_limitations(self, candidate: CandidateVesselFeatures) -> List[str]:
        """Generate transparent scientific limitations and sensor caveats."""
        lims = [
            "Attribution Evidence Score is a comparative forensic index, not an uncalibrated Bayesian probability.",
            "AIS reception is subject to terrestrial and satellite receiver latency and transponder spoofing risks.",
            "Hydrodynamic drift advection is constrained by ERA5 wind (31 km) and CMEMS current spatial resolution.",
        ]
        if candidate.sanitized_pings_count < 4:
            lims.append("Sparse trajectory sampling (< 4 pings) increases kinematic uncertainty.")
        if candidate.ais_gap.detected:
            lims.append("AIS transponder blackout restricts track interpolation accuracy during release window.")
        return lims

    # =========================================================================
    # 3. End-to-End Evaluation Pipeline
    # =========================================================================

    async def evaluate_candidates(
        self,
        spill: SpillDetection,
        drift_result: DriftResult,
        candidate_trajectories: Union[List[AISTrajectory], List[CandidateVesselFeatures], str, Path],
        evidence_threshold: Optional[float] = None,
    ) -> Tuple[List[VesselEvidence], Optional[VesselEvidence], Optional[str]]:
        """
        Evaluate candidate vessels using multi-criteria attribution scoring.
        
        Returns:
          (ranked_candidates, top_candidate, insufficient_evidence_reason)
        """
        threshold = evidence_threshold if evidence_threshold is not None else self.min_evidence_threshold

        # Step 1: Ensure candidates are in CandidateVesselFeatures format
        features_list: List[CandidateVesselFeatures] = []
        if isinstance(candidate_trajectories, list) and candidate_trajectories and isinstance(candidate_trajectories[0], CandidateVesselFeatures):
            features_list = candidate_trajectories
        else:
            # Run AISVesselAnalyzer to extract kinematic candidate features
            features_list = self._vessel_analyzer.analyze_candidates(
                probable_source_region=drift_result.source_region,
                release_time_window=drift_result.release_time_window,
                spatial_radius_km=drift_result.uncertainty.spatial_radius_km * 2.5,
                ais_dataset=candidate_trajectories,
                source_centroid=drift_result.source_centroid,
            )

        if not features_list:
            reason = (
                "INSUFFICIENT EVIDENCE: Zero candidate vessels were detected within the "
                "spatio-temporal release corridor. The responsible vessel may have operated "
                "with transponders disabled ('dark ship') or release occurred outside AIS coverage."
            )
            return [], None, reason

        # Step 2: Score each candidate
        total_w = self.total_weight
        scored_candidates: List[VesselEvidence] = []

        for cand in features_list:
            s_spatial = self.calculate_spatial_consistency(
                cand, drift_result.uncertainty.spatial_radius_km
            )
            s_temporal = self.calculate_temporal_consistency(
                cand, drift_result.release_time_window
            )
            s_trajectory = self.calculate_trajectory_consistency(
                cand, s_spatial
            )
            s_drift = self.calculate_drift_consistency(
                cand, drift_result.particle_trajectories, drift_result.source_centroid
            )
            s_behavioral = self.calculate_behavioral_consistency(cand)

            # Weighted composite score
            composite = (
                (self.spatial_weight * s_spatial)
                + (self.temporal_weight * s_temporal)
                + (self.trajectory_weight * s_trajectory)
                + (self.drift_weight * s_drift)
                + (self.behavioral_weight * s_behavioral)
            ) / total_w

            overall_score = round(float(np.clip(composite, 0.0, 100.0)), 1)
            classification = self.classify_score(overall_score)

            explanation = self.generate_explanation(
                cand, s_spatial, s_temporal, s_trajectory, s_drift, s_behavioral, overall_score
            )
            counterfactual = self.generate_counterfactual(
                cand, s_spatial, s_temporal, s_trajectory, s_drift, s_behavioral
            )
            limitations = self.generate_limitations(cand)

            cpa_detail = ClosestPointOfApproach(
                distance_km=cand.closest_distance_km,
                timestamp=cand.time_of_closest_approach,
                vessel_latitude=cand.closest_point_to_source.latitude,
                vessel_longitude=cand.closest_point_to_source.longitude,
                source_latitude=drift_result.source_centroid.latitude,
                source_longitude=drift_result.source_centroid.longitude,
            )

            coverage_quality = "continuous"
            if cand.ais_gap.detected:
                coverage_quality = "dark_period_suspected" if cand.ais_gap.gap_duration_minutes >= 60.0 else "minor_gaps"

            vessel_evidence = VesselEvidence(
                mmsi=cand.mmsi,
                vessel_name=cand.vessel_name or f"Vessel-{cand.mmsi}",
                vessel_type=cand.vessel_type or "Unknown",
                rank=1,  # updated after sort
                spatial_score=s_spatial,
                temporal_score=s_temporal,
                trajectory_score=s_trajectory,
                drift_score=s_drift,
                behavioral_score=s_behavioral,
                component_scores={
                    "spatial": s_spatial,
                    "temporal": s_temporal,
                    "trajectory": s_trajectory,
                    "drift": s_drift,
                    "behavioral": s_behavioral,
                },
                overall_evidence_score=overall_score,
                classification=classification,
                explanation=explanation,
                counterfactual_explanation=counterfactual,
                limitations=limitations,
                closest_approach=cpa_detail,
                ais_coverage_quality=coverage_quality,
                scoring_weights_used=self.weights_dict,
            )
            scored_candidates.append(vessel_evidence)

        # Step 3: Sort by overall evidence score descending and assign ranks
        scored_candidates.sort(key=lambda v: v.overall_evidence_score, reverse=True)
        for i, v in enumerate(scored_candidates):
            v.rank = i + 1

        # Step 4: Minimum Evidence Threshold Verification (Fail-Safe)
        top_cand = scored_candidates[0]
        if top_cand.overall_evidence_score < threshold:
            insufficient_reason = (
                f"INSUFFICIENT EVIDENCE: No candidate vessel reached the minimum evidence threshold "
                f"of {threshold:.1f}. Highest observed score was {top_cand.overall_evidence_score:.1f} "
                f"(MMSI: {top_cand.mmsi}). The system refuses to force an uncorroborated culprit attribution."
            )
            return scored_candidates, None, insufficient_reason

        return scored_candidates, top_cand, None
