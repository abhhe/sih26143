import logging
from fastapi import APIRouter
from backend.app.domain.models import ValidationMetrics
from backend.app.adapters.validation.benchmark_validator import SyntheticBenchmarkValidator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Scientific Validation"])
validator = SyntheticBenchmarkValidator()


@router.get(
    "/api/validation/metrics",
    response_model=ValidationMetrics,
    summary="Retrieve scientific validation metrics and sensitivity matrix across synthetic ground-truth scenarios",
)
async def get_validation_metrics() -> ValidationMetrics:
    return validator.evaluate_benchmark(num_runs=25)


@router.post(
    "/api/validation/run",
    response_model=ValidationMetrics,
    summary="Execute fresh Monte Carlo synthetic benchmark validation runs",
)
async def run_validation_benchmark(num_runs: int = 25) -> ValidationMetrics:
    return validator.evaluate_benchmark(num_runs=max(5, min(100, num_runs)))
