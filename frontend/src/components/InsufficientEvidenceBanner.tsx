import React from 'react';
import { ShieldX, Info } from 'lucide-react';

interface InsufficientEvidenceBannerProps {
  reason: string;
  threshold?: number;
  highestCandidateScore?: number;
}

export const InsufficientEvidenceBanner: React.FC<InsufficientEvidenceBannerProps> = ({
  reason,
  threshold = 50.0,
  highestCandidateScore,
}) => {
  return (
    <div className="insufficient-banner">
      <div className="banner-icon-box">
        <ShieldX size={28} className="text-rose" />
      </div>

      <div className="banner-content">
        <div className="banner-title-row">
          <h4 className="banner-title">INSUFFICIENT ATTRIBUTION EVIDENCE</h4>
          <span className="badge badge-insufficient">
            THRESHOLD: {threshold.toFixed(1)} / 100
          </span>
          {highestCandidateScore !== undefined && (
            <span className="badge badge-low">
              PEAK CANDIDATE: {highestCandidateScore.toFixed(1)} / 100
            </span>
          )}
        </div>

        <p className="banner-reason">{reason}</p>

        <div className="banner-subtext">
          <Info size={14} className="inline-icon" />
          <span>
            The system adheres strictly to scientific integrity standards: When physical dispersion envelopes, time windows, and kinematic AIS correlation do not converge above calibrated evidentiary bounds, attribution is explicitly withheld to prevent false accusations.
          </span>
        </div>
      </div>
    </div>
  );
};
