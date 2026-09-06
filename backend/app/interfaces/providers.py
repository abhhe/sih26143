from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Tuple, Protocol, runtime_checkable

from backend.app.domain.models import (
    SatelliteObservation,
    SpillDetection,
    EnvironmentalState,
    EnvironmentalGridSnapshot,
    AISPoint,
    AISTrajectory,
    DriftResult,
    VesselEvidence,
    BoundingBox,
)


@runtime_checkable
class ISatelliteObservationProvider(Protocol):
    """
    Interface for fetching or reading satellite SAR observation data.
    Implementations:
      - CopernicusDataSpaceAdapter (CDSE OData/STAC API)
      - CSIRODatasetAdapter (Local Sentinel-1 benchmark)
      - LocalGeoTIFFAdapter
      - MockSatelliteProvider (Pre-packaged test scenes)
    """
    async def get_observation_by_id(self, image_id: str) -> SatelliteObservation:
        ...

    async def search_scenes(
        self,
        bounding_box: BoundingBox,
        start_time: datetime,
        end_time: datetime,
        sensor: str = "Sentinel-1",
    ) -> List[SatelliteObservation]:
        ...


@runtime_checkable
class ISpillDetectionEngine(Protocol):
    """
    Interface for satellite oil spill segmentation and morphology extraction.
    Implementations:
      - PyTorchUNetDetectionEngine (Deep learning segmentation on VV SAR)
      - AdaptiveThresholdDetectionEngine (CFAR / Lee speckle filter + Otsu morphology)
      - BenchmarkGroundTruthDetector (Direct retrieval from labeled test dataset)
    """
    async def detect_spill(
        self, observation: SatelliteObservation, confidence_threshold: float = 0.5
    ) -> SpillDetection:
        ...


@runtime_checkable
class IMeteoOceanProvider(Protocol):
    """
    Interface for environmental wind and ocean current vector fields.
    Implementations:
      - ERA5AndCMEMSNetCDFAdapter (Local or CDS/Copernicus Marine NetCDF/GRIB)
      - OpenMeteoMarineAPIAdapter
      - MockEnvironmentalProvider (Standardized synthetic vortex / advection fields)
    """
    async def get_environmental_state(
        self, latitude: float, longitude: float, timestamp: datetime
    ) -> EnvironmentalState:
        ...

    async def get_grid_slice(
        self,
        bounding_box: BoundingBox,
        start_time: datetime,
        end_time: datetime,
        step_hours: int = 1,
    ) -> List[EnvironmentalGridSnapshot]:
        ...


@runtime_checkable
class IAISTrajectoryProvider(Protocol):
    """
    Interface for historical AIS vessel trajectory ingestion.
    Implementations:
      - NOAA MarineCadastreAdapter (Direct CSV / Parquet querying)
      - GlobalFishingWatchAPIAdapter
      - SpireOrAISStreamAdapter
      - MockAISProvider (Realistic maritime traffic generator with synthetic culprits)
    """
    async def query_trajectories(
        self,
        bounding_box: BoundingBox,
        start_time: datetime,
        end_time: datetime,
        vessel_types: Optional[List[str]] = None,
    ) -> List[AISTrajectory]:
        ...


@runtime_checkable
class IHindcastDriftEngine(Protocol):
    """
    Interface for backward Lagrangian Monte Carlo slick drift hindcasting.
    Implementations:
      - MonteCarloLagrangianDriftEngine (NumPy/SciPy RK2 backward advection + leeway + diffusion)
      - OpenDriftWrapperEngine (Production python open-source ocean drift framework wrapper)
    """
    async def compute_backward_drift(
        self,
        spill: SpillDetection,
        observation_time: datetime,
        metocean_provider: IMeteoOceanProvider,
        max_hindcast_hours: float = 48.0,
        particle_count: int = 500,
        leeway_factor: float = 0.032,
        leeway_deflection_deg: float = 0.0,
        horizontal_diffusivity: float = 5.0,
    ) -> DriftResult:
        ...


@runtime_checkable
class IAttributionScoringEngine(Protocol):
    """
    Interface for explainable multi-criteria Attribution Evidence Scoring.
    Implementations:
      - ExplainableMultiCriteriaScoringEngine (Spatial + Temporal + Trajectory + Drift + Behavior)
    """
    async def evaluate_candidates(
        self,
        spill: SpillDetection,
        drift_result: DriftResult,
        candidate_trajectories: List[AISTrajectory],
        evidence_threshold: float = 50.0,
    ) -> Tuple[List[VesselEvidence], Optional[VesselEvidence], Optional[str]]:
        """
        Returns:
          - candidate_evidences: ranked list of VesselEvidence
          - top_candidate: highest-scoring vessel, or None if Insufficient Evidence
          - insufficient_evidence_reason: explanation if threshold was not reached
        """
        ...
