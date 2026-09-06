import React from 'react';
import { VesselEvidence } from '../types/contracts';
import { ShieldCheck, AlertCircle } from 'lucide-react';

interface EvidencePanelProps {
  vessel: VesselEvidence | null;
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ vessel }) => {
  if (!vessel) {
    return (
      <div className="card evidence-panel empty-state">
        <AlertCircle size={24} className="text-muted" />
        <p className="text-muted">Select a candidate vessel from the table or map to inspect its explainable attribution evidence dossier.</p>
      </div>
    );
  }

  const cpaTimeUtc = new Date(vessel.closest_approach.timestamp)
    .toUTCString()
    .replace('GMT', 'UTC');

  const isPhase5 = !!vessel.candidate_features;

  // Classification styling
  let badgeClass = 'badge-insufficient';
  if (vessel.classification === 'High Evidence' || vessel.classification === 'Strong Candidate') badgeClass = 'badge-high';
  else if (vessel.classification === 'Medium Evidence' || vessel.classification === 'Moderate Candidate') badgeClass = 'badge-medium';
  else if (vessel.classification === 'Low Evidence' || vessel.classification === 'Low Consistency') badgeClass = 'badge-low';

  return (
    <div className="card evidence-panel">
      <div className="card-header">
        <div className="card-title-group">
          <ShieldCheck size={16} className="text-cyan" />
          <h3 className="card-title">
            {isPhase5 ? 'Candidate Vessel Kinematic Evidence (Phase 5)' : 'Forensic Attribution Evidence Dossier'}
          </h3>
        </div>
        <span className={`badge ${badgeClass}`}>
          {isPhase5 ? 'Candidate Vessel' : vessel.classification}
        </span>
      </div>

      <div className="card-body">
        {/* Top summary row: Vessel Name, MMSI, Overall Score */}
        <div className="evidence-hero">
          <div>
            <div className="hero-vessel-name">{vessel.vessel_name || 'Candidate Vessel'}</div>
            <div className="hero-meta font-mono">
              <span>MMSI: {vessel.mmsi}</span> &bull; <span>Type: {vessel.vessel_type || 'Cargo/Tanker'}</span>
            </div>
          </div>

          <div className="hero-score-box">
            <span className="hero-score-label">
              {isPhase5 ? 'Kinematic Compatibility' : 'Attribution Evidence Score'}
            </span>
            <div className="hero-score-val font-mono">
              {isPhase5 ? (
                <span style={{ fontSize: '1.2rem', color: '#00e5ff' }}>
                  {vessel.candidate_features?.entered_source_region ? 'SOURCE INTERSECT' : 'CORRIDOR MATCH'}
                </span>
              ) : (
                <>
                  <span>{vessel.overall_evidence_score.toFixed(1)}</span>
                  <span className="hero-score-scale">/100</span>
                </>
              )}
            </div>
            <span className="hero-score-subtext">
              {isPhase5 ? 'Spatial & Temporal Correlation' : 'Calibrated multi-criteria index'}
            </span>
          </div>
        </div>

        {/* Closest Point of Approach (CPA) Banner */}
        <div className="cpa-banner">
          <div className="cpa-item">
            <span className="cpa-label">CPA Distance</span>
            <span className="cpa-value font-mono">
              {vessel.closest_approach.distance_km.toFixed(2)} km
            </span>
          </div>
          <div className="cpa-item">
            <span className="cpa-label">CPA Timestamp (UTC)</span>
            <span className="cpa-value font-mono">{cpaTimeUtc}</span>
          </div>
          <div className="cpa-item">
            <span className="cpa-label">Vessel Position at CPA</span>
            <span className="cpa-value font-mono">
              {vessel.closest_approach.vessel_latitude.toFixed(4)}°N,{' '}
              {vessel.closest_approach.vessel_longitude.toFixed(4)}°E
            </span>
          </div>
          <div className="cpa-item">
            <span className="cpa-label">AIS Transponder Status</span>
            <span
              className={`font-mono font-semibold ${
                vessel.ais_coverage_quality === 'continuous'
                  ? 'text-emerald'
                  : 'text-rose'
              }`}
            >
              {vessel.ais_coverage_quality === 'continuous'
                ? 'CONTINUOUS BROADCAST'
                : 'SUSPECTED DARK PERIOD'}
            </span>
          </div>
        </div>

        {/* Consistency Factor Breakdown Bars */}
        <div className="factors-section">
          <h4 className="section-subtitle">Consistency Metrics Breakdown</h4>
          <div className="factors-grid">
            <div className="factor-item">
              <div className="factor-header">
                <span className="factor-name">Spatial Consistency</span>
                <span className="factor-val font-mono">{vessel.spatial_score.toFixed(1)}%</span>
              </div>
              <div className="progress-bar-bg">
                <div
                  className="progress-bar-fill fill-emerald"
                  style={{ width: `${vessel.spatial_score}%` }}
                ></div>
              </div>
            </div>

            <div className="factor-item">
              <div className="factor-header">
                <span className="factor-name">Temporal Consistency</span>
                <span className="factor-val font-mono">{vessel.temporal_score.toFixed(1)}%</span>
              </div>
              <div className="progress-bar-bg">
                <div
                  className="progress-bar-fill fill-emerald"
                  style={{ width: `${vessel.temporal_score}%` }}
                ></div>
              </div>
            </div>

            <div className="factor-item">
              <div className="factor-header">
                <span className="factor-name">Trajectory Corridor Overlap</span>
                <span className="factor-val font-mono">{vessel.trajectory_score.toFixed(1)}%</span>
              </div>
              <div className="progress-bar-bg">
                <div
                  className="progress-bar-fill fill-cyan"
                  style={{ width: `${vessel.trajectory_score}%` }}
                ></div>
              </div>
            </div>

            <div className="factor-item">
              <div className="factor-header">
                <span className="factor-name">Lagrangian Drift Intersect</span>
                <span className="factor-val font-mono">{vessel.drift_score.toFixed(1)}%</span>
              </div>
              <div className="progress-bar-bg">
                <div
                  className="progress-bar-fill fill-cyan"
                  style={{ width: `${vessel.drift_score}%` }}
                ></div>
              </div>
            </div>

            {vessel.behavioral_score !== undefined && vessel.behavioral_score !== null && (
              <div className="factor-item">
                <div className="factor-header">
                  <span className="factor-name">Behavioral Anomaly Index</span>
                  <span className="factor-val font-mono">{vessel.behavioral_score.toFixed(1)}%</span>
                </div>
                <div className="progress-bar-bg">
                  <div
                    className="progress-bar-fill fill-amber"
                    style={{ width: `${vessel.behavioral_score}%` }}
                  ></div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Explainability Justification Bullet Points */}
        <div className="audit-section">
          <h4 className="section-subtitle">Attribution Justification & Scientific Audit Trail</h4>
          <ul className="audit-bullets">
            {vessel.explanation.map((bullet, idx) => (
              <li key={idx} className="audit-bullet-item">
                <span className="bullet-marker">&bull;</span>
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Scientific Principle Reminder */}
        <div className="scientific-disclaimer">
          <strong>Scientific Principle:</strong>{' '}
          {isPhase5
            ? 'Vessel is evaluated strictly as a candidate based on spatial and temporal compatibility with the probable source region. Final attribution scoring and culpability analysis will be evaluated in Phase 6.'
            : 'This metric represents an Attribution Evidence Score derived from physical drift hindcasting and AIS kinematic correlation. It is not an uncalibrated statistical probability of culpability.'}
        </div>
      </div>
    </div>
  );
};
