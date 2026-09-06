import { API_BASE_URL } from '../config/api';
import { SpillDetection, ValidationMetrics } from '../types/contracts';

export interface HealthResponse {
  status: string;
  mode: string;
  service: string;
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
};
