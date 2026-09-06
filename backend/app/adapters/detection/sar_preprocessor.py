import numpy as np
import scipy.ndimage as ndi
from typing import Tuple, Optional


class SARPreprocessor:
    """
    SAR Radiometric Preprocessor and Speckle Suppression Filter.
    
    Specialized for Sentinel-1 C-band SAR GRD products (VV and VH polarizations).
    Features:
      - Radiometric intensity to backscatter (sigma0 in dB)
      - Percentile contrast stretching
      - Refined Lee adaptive speckle filter (preserving dark slick edges while smoothing clutter)
    """

    @staticmethod
    def to_decibels(intensity: np.ndarray, eps: float = 1e-7) -> np.ndarray:
        """
        Convert linear SAR backscatter intensity to decibels (dB).
        sigma_0 (dB) = 10 * log10(max(intensity, eps))
        """
        arr = np.maximum(intensity.astype(np.float32), eps)
        return 10.0 * np.log10(arr)

    @staticmethod
    def percentile_normalize(
        arr: np.ndarray, p_low: float = 1.0, p_high: float = 99.0
    ) -> np.ndarray:
        """
        Robust percentile normalization to [0.0, 1.0] range.
        Suppresses extreme outlier radar specular bounces and radar shadow zeroes.
        """
        v_min = float(np.percentile(arr, p_low))
        v_max = float(np.percentile(arr, p_high))
        if v_max - v_min < 1e-6:
            return np.zeros_like(arr, dtype=np.float32)
        clipped = np.clip(arr, v_min, v_max)
        return (clipped - v_min) / (v_max - v_min)

    @staticmethod
    def lee_filter(
        img: np.ndarray, window_size: int = 7, enl: float = 4.4
    ) -> np.ndarray:
        """
        Adaptive Lee Speckle Filter for SAR imagery.
        
        Parameters:
          img: 2D numpy array (float32, normalized or intensity)
          window_size: Odd integer kernel size (e.g. 5, 7)
          enl: Equivalent Number of Looks (Sentinel-1 IW GRD ENL is typically ~4.4)
          
        Mathematical formulation:
          W = 1 - (C_noise^2 / C_local^2)
          Filtered = Local_Mean + W * (Input - Local_Mean)
          where C_noise = 1 / sqrt(ENL)
        """
        img_f = img.astype(np.float32)

        # 1. Local spatial mean
        local_mean = ndi.uniform_filter(img_f, size=window_size)

        # 2. Local variance via Var(X) = E[X^2] - (E[X])^2
        local_mean_sq = ndi.uniform_filter(img_f**2, size=window_size)
        local_var = np.maximum(0.0, local_mean_sq - local_mean**2)

        # 3. Noise relative variance based on Equivalent Number of Looks (ENL)
        noise_rel_var = 1.0 / max(1.0, enl)

        # 4. Local coefficient of variation squared: C_local^2 = Var / (Mean^2 + eps)
        local_cv_sq = local_var / (local_mean**2 + 1e-6)

        # 5. Weight factor: W = max(0, 1 - C_noise^2 / C_local^2)
        weights = np.maximum(0.0, 1.0 - (noise_rel_var / (local_cv_sq + 1e-6)))
        weights = np.minimum(1.0, weights)

        # 6. Adaptive combination
        filtered = local_mean + weights * (img_f - local_mean)
        return filtered.astype(np.float32)
