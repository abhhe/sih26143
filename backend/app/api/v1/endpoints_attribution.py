import logging
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from backend.app.domain.models import (
    SpillDetection,
    DriftResult,
    CandidateVesselFeatures,
    VesselEvidence,
)
from backend.app.adapters.attribution.attribution_engine import ExplainableAttributionEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Explainable Vessel Attribution"])


class AttributionEvaluationRequest(BaseModel):
    spill: SpillDetection = Field(..., description="Observed oil spill characterization")
    drift_result: DriftResult = Field(..., description="Lagrangian backward hindcast result")
    candidate_features: Optional[List[CandidateVesselFeatures]] = Field(
        None, description="Pre-analyzed candidate vessel kinematic features"
    )
    ais_dataset_path: Optional[str] = Field(
        None, description="Optional path to AIS trajectory CSV to analyze on-the-fly"
    )
    evidence_threshold: float = Field(
        default=50.0, ge=10.0, le=95.0, description="Minimum evidence threshold for culpability"
    )
    weights: Optional[Dict[str, float]] = Field(
        None, description="Optional custom weights for spatial, temporal, trajectory, drift, behavioral"
    )


class AttributionEvaluationResponse(BaseModel):
    candidates: List[VesselEvidence]
    top_candidate: Optional[VesselEvidence] = None
    insufficient_evidence_reason: Optional[str] = None
    threshold_used: float
    weights_used: Dict[str, float]


@router.post(
    "/api/attribution/evaluate",
    response_model=AttributionEvaluationResponse,
    summary="Evaluate candidate vessels using explainable multi-criteria Attribution Evidence Scoring",
    description=(
        "Correlates oil spill observation, Lagrangian backward drift particles, and AIS trajectories. "
        "Calculates Spatial, Temporal, Trajectory, Drift, and Behavioral consistency metrics. "
        "Produces an Attribution Evidence Score [0-100] (not a probability), rank, classification, "
        "counterfactual explanation, and transparent scientific limitations. "
        "Enforces an 'INSUFFICIENT EVIDENCE' fail-safe if no candidate passes the evidence threshold."
    ),
)
async def evaluate_vessel_attribution(
    request: AttributionEvaluationRequest = Body(...),
) -> AttributionEvaluationResponse:
    try:
        # Configure custom weights if provided
        kwargs = {"min_evidence_threshold": request.evidence_threshold}
        if request.weights:
            if "spatial" in request.weights:
                kwargs["spatial_weight"] = request.weights["spatial"]
            if "temporal" in request.weights:
                kwargs["temporal_weight"] = request.weights["temporal"]
            if "trajectory" in request.weights:
                kwargs["trajectory_weight"] = request.weights["trajectory"]
            if "drift" in request.weights:
                kwargs["drift_weight"] = request.weights["drift"]
            if "behavioral" in request.weights:
                kwargs["behavioral_weight"] = request.weights["behavioral"]

        engine = ExplainableAttributionEngine(**kwargs)

        input_candidates = request.candidate_features or request.ais_dataset_path
        if input_candidates is None:
            # Default to local demo fixture
            from pathlib import Path
            input_candidates = Path("tests/fixtures/marine_cadastre_ais_fixture.csv")

        candidates, top_cand, reason = await engine.evaluate_candidates(
            spill=request.spill,
            drift_result=request.drift_result,
            candidate_trajectories=input_candidates,
            evidence_threshold=request.evidence_threshold,
        )

        return AttributionEvaluationResponse(
            candidates=candidates,
            top_candidate=top_cand,
            insufficient_evidence_reason=reason,
            threshold_used=request.evidence_threshold,
            weights_used=engine.weights_dict,
        )
    except Exception as e:
        logger.error(f"Error during attribution evaluation: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
