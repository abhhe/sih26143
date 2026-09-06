import { API_BASE_URL } from '../config/api';
import {
  SpillDetection,
  ValidationMetrics,
  DriftResult,
  EnvironmentalState,
  SpillGeometry,
  CoordinatePoint,
  DriftUncertainty,
  ReleaseTimeWindow,
  ParticleTrajectory,
  CandidateVesselFeatures,
  AISCandidateRequest,
} from '../types/contracts';

export interface HealthResponse {
  status: string;
  mode: string;
  service: string;
}

export interface MetoceanPointRequest {
  latitude: number;
  longitude: number;
  timestamp?: string;
  wind_speed_ms?: number;
  wind_direction_deg?: number;
  current_speed_ms?: number;
  current_direction_deg?: number;
  wind_u?: number;
  wind_v?: number;
  current_u?: number;
  current_v?: number;
}

export interface DriftSimulationRequest {
  spill?: SpillDetection;
  latitude?: number;
  longitude?: number;
  area_km2?: number;
  observation_time?: string;
  max_hindcast_hours?: number;
  backward_hours?: number;
  forecast_hours?: number;
  particle_count?: number;
  timestep_minutes?: number;
  time_step_minutes?: number;
  leeway_factor?: number;
  leeway_deflection_deg?: number;
  horizontal_diffusivity?: number;
  random_seed?: number;
  wind_speed_ms?: number;
  wind_direction_deg?: number;
  current_speed_ms?: number;
  current_direction_deg?: number;
  wind_u?: number;
  wind_v?: number;
  current_u?: number;
  current_v?: number;
}

export interface DriftSimulationResponse {
  drift_result: DriftResult;
  environmental_snapshot: EnvironmentalState;
  model_parameters: Record<string, any>;
}

export interface SourceReconstructionResponse {
  source_region: SpillGeometry;
  source_region_50?: SpillGeometry;
  source_region_90?: SpillGeometry;
  source_centroid: CoordinatePoint;
  uncertainty: DriftUncertainty;
  release_window: ReleaseTimeWindow;
  backward_trajectory: ParticleTrajectory[];
  forward_trajectory?: ParticleTrajectory[];
  environmental_snapshot: EnvironmentalState;
  quality: Record<string, any>;
  scientific_disclaimer: string;
}

export class ApiError extends Error {
  statusCode?: number;
  detail?: string;

  constructor(message: string, statusCode?: number, detail?: string) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

/**
 * Centralized API Client for SIH PS-26143 FastAPI Backend.
 * Uses configurable VITE_API_BASE_URL and enforces strict scientific integrity.
 */
export const apiClient = {
  /**
   * Ping system health endpoint (/api/health).
   */
  async checkHealth(timeoutMs = 4000): Promise<HealthResponse> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${API_BASE_URL}/api/health`, {
        method: 'GET',
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
        },
      });

      if (!res.ok) {
        throw new ApiError(`Health check failed with HTTP ${res.status}`, res.status);
      }

      return (await res.json()) as HealthResponse;
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        throw new ApiError(`Backend health check timed out after ${timeoutMs}ms`, 408);
      }
      if (err instanceof ApiError) {
        throw err;
      }
      throw new ApiError(
        `Backend offline or unreachable at ${API_BASE_URL}`,
        0,
        (err as Error).message
      );
    } finally {
      clearTimeout(timer);
    }
  },

  /**
   * Upload and process SAR raster imagery via /api/satellite/analyze.
   * Sends multipart/form-data containing the actual SAR raster file and acquisition parameters.
   */
  async analyzeSarImage(formData: FormData, timeoutMs = 45000): Promise<SpillDetection> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${API_BASE_URL}/api/satellite/analyze`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
        // Notice: Do NOT set Content-Type header here; browser sets multipart/form-data boundary automatically
      });

      if (!res.ok) {
        let errorDetail = '';
        try {
          const errData = await res.json();
          errorDetail = errData.detail || JSON.stringify(errData);
        } catch {
          errorDetail = res.statusText || `HTTP ${res.status}`;
        }

        if (res.status === 400) {
          throw new ApiError(errorDetail || 'Invalid or unsupported SAR file.', 400, errorDetail);
        } else if (res.status === 422) {
          throw new ApiError(`Validation error in request parameters: ${errorDetail}`, 422, errorDetail);
        } else {
          throw new ApiError(
            `SAR processing failure on backend (HTTP ${res.status}): ${errorDetail}`,
            res.status,
            errorDetail
          );
        }
      }

      const detection = (await res.json()) as SpillDetection;

      // Validate core response schema
      if (typeof detection.detected !== 'boolean' || typeof detection.confidence !== 'number') {
        throw new ApiError(
          'Malformed backend response: Missing required detection boolean or confidence score.',
          502
        );
      }

      return detection;
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        throw new ApiError(
          `SAR analysis request timed out after ${timeoutMs / 1000}s. The backend may be processing a large raster.`,
          408
        );
      }
      if (err instanceof ApiError) {
        throw err;
      }
      throw new ApiError(
        `Cannot connect to FastAPI backend at ${API_BASE_URL}. Ensure the backend service is running on port 8000.`,
        0,
        (err as Error).message
      );
    } finally {
      clearTimeout(timer);
    }
  },

  /**
   * Retrieve synthetic Monte Carlo validation metrics.
   */
  async getValidationMetrics(): Promise<ValidationMetrics> {
    const res = await fetch(`${API_BASE_URL}/api/validation/metrics`);
    if (!res.ok) {
      throw new ApiError(`Failed to fetch validation metrics: HTTP ${res.status}`, res.status);
    }
    return (await res.json()) as ValidationMetrics;
  },

  /**
   * Trigger validation benchmark run.
   */
  async runValidationBenchmark(numRuns = 50): Promise<ValidationMetrics> {
    const res = await fetch(`${API_BASE_URL}/api/validation/run?num_runs=${numRuns}`, {
      method: 'POST',
    });
    if (!res.ok) {
      throw new ApiError(`Failed to run benchmark: HTTP ${res.status}`, res.status);
    }
    return (await res.json()) as ValidationMetrics;
  },

  /**
   * Query metocean wind and ocean currents at a geographic point (/api/metocean/point).
   */
  async getMetoceanPoint(request: MetoceanPointRequest, timeoutMs = 10000): Promise<EnvironmentalState> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${API_BASE_URL}/api/metocean/point`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new ApiError(errData.detail || `Metocean query failed (HTTP ${res.status})`, res.status);
      }

      return (await res.json()) as EnvironmentalState;
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        throw new ApiError(`Metocean request timed out after ${timeoutMs}ms`, 408);
      }
      if (err instanceof ApiError) throw err;
      throw new ApiError(`Error connecting to metocean API: ${(err as Error).message}`, 0);
    } finally {
      clearTimeout(timer);
    }
  },

  /**
   * Run Runge-Kutta 2nd-order (RK2) Lagrangian backward drift hindcasting (/api/drift/simulate).
   */
  async simulateDrift(request: DriftSimulationRequest, timeoutMs = 25000): Promise<DriftSimulationResponse> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${API_BASE_URL}/api/drift/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new ApiError(errData.detail || `Drift simulation failed (HTTP ${res.status})`, res.status);
      }

      return (await res.json()) as DriftSimulationResponse;
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        throw new ApiError(`Drift simulation timed out after ${timeoutMs}ms`, 408);
      }
      if (err instanceof ApiError) throw err;
      throw new ApiError(`Error connecting to drift simulation API: ${(err as Error).message}`, 0);
    } finally {
      clearTimeout(timer);
    }
  },

  /**
   * Run backward Lagrangian source reconstruction to estimate Probable Source Region (/api/drift/source-reconstruction).
   */
  async reconstructSource(request: DriftSimulationRequest, timeoutMs = 25000): Promise<SourceReconstructionResponse> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${API_BASE_URL}/api/drift/source-reconstruction`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new ApiError(errData.detail || `Source reconstruction failed (HTTP ${res.status})`, res.status);
      }

      return (await res.json()) as SourceReconstructionResponse;
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        throw new ApiError(`Source reconstruction timed out after ${timeoutMs}ms`, 408);
      }
      if (err instanceof ApiError) throw err;
      throw new ApiError(`Error connecting to source reconstruction API: ${(err as Error).message}`, 0);
    } finally {
      clearTimeout(timer);
    }
  },

  /**
   * Analyze AIS vessel trajectories and extract candidate kinematic features (/api/ais/analyze-candidates).
   * Spatially and temporally filters historical tracks against Phase 4 probable source region.
   */
  async analyzeAisCandidates(
    request: AISCandidateRequest,
    timeoutMs = 25000
  ): Promise<CandidateVesselFeatures[]> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${API_BASE_URL}/api/ais/analyze-candidates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new ApiError(
          errData.detail || `AIS candidate analysis failed (HTTP ${res.status})`,
          res.status
        );
      }

      return (await res.json()) as CandidateVesselFeatures[];
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        throw new ApiError(`AIS candidate analysis timed out after ${timeoutMs}ms`, 408);
      }
      if (err instanceof ApiError) throw err;
      throw new ApiError(`Error connecting to AIS candidate API: ${(err as Error).message}`, 0);
    } finally {
      clearTimeout(timer);
    }
  },
};

