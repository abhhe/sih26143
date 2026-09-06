import React from 'react';
import { VesselEvidence } from '../types/contracts';
import { Ship, ChevronRight } from 'lucide-react';

interface CandidateTableProps {
  candidates: VesselEvidence[];
  selectedMmsi?: string | null;
  onSelectVessel: (mmsi: string) => void;
}

export const CandidateTable: React.FC<CandidateTableProps> = ({
  candidates,
  selectedMmsi,
  onSelectVessel,
}) => {
  if (!candidates || candidates.length === 0) {
    return (
      <div className="card candidate-table-card">
        <div className="card-header">
          <div className="card-title-group">
            <Ship size={16} className="text-muted" />
            <h3 className="card-title">Candidate Vessel Correlation & Scoring</h3>
          </div>
          <span className="badge badge-low">Not available</span>
        </div>
        <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
          <p style={{ margin: 0, fontSize: '0.9rem' }}>
            No AIS candidate vessels evaluated. Phase 2 strictly executes SAR spill detection. AIS spatiotemporal correlation will be evaluated in Phase 4.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="card candidate-table-card">
      <div className="card-header">
        <div className="card-title-group">
          <Ship size={16} className="text-cyan" />
          <h3 className="card-title">Candidate Vessel Correlation & Scoring</h3>
        </div>
        <span className="card-hint">
          Click any vessel to inspect explainable evidence dossier
        </span>
      </div>

      <div className="table-responsive">
        <table className="candidate-table">
          <thead>
            <tr>
              <th style={{ width: '45px' }}>Rank</th>
              <th>Vessel Identification</th>
              <th>Type</th>
              <th title="Proximity to hindcast source at release time">Spatial</th>
              <th title="Alignment with release time window">Temporal</th>
              <th title="Intersection with slick drift corridor">Trajectory</th>
              <th title="Monte Carlo particle density intersection">Drift</th>
              <th title="Speed drops, maneuvers, or AIS gaps">Behavioral</th>
              <th title="Attribution Evidence Score (0-100)">Evidence Score</th>
              <th>Classification</th>
              <th style={{ width: '30px' }}></th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((vessel, index) => {
              const isSelected = vessel.mmsi === selectedMmsi;
              const rank = index + 1;

              // Classification Badge style
              let badgeClass = 'badge-insufficient';
              if (vessel.classification === 'High Evidence') badgeClass = 'badge-high';
              else if (vessel.classification === 'Medium Evidence') badgeClass = 'badge-medium';
              else if (vessel.classification === 'Low Evidence') badgeClass = 'badge-low';

              return (
                <tr
                  key={vessel.mmsi}
                  className={`candidate-row ${isSelected ? 'row-selected' : ''}`}
                  onClick={() => onSelectVessel(vessel.mmsi)}
                >
                  <td className="font-mono text-center text-muted">{rank}</td>
                  <td>
                    <div className="vessel-identity">
                      <span className="vessel-name font-semibold">
                        {vessel.vessel_name || 'Unknown Vessel'}
                      </span>
                      <span className="vessel-mmsi font-mono text-muted">
                        MMSI: {vessel.mmsi}
                      </span>
                    </div>
                  </td>
                  <td className="text-muted">{vessel.vessel_type || 'Cargo'}</td>
                  <td className="font-mono">{vessel.spatial_score.toFixed(1)}</td>
                  <td className="font-mono">{vessel.temporal_score.toFixed(1)}</td>
                  <td className="font-mono">{vessel.trajectory_score.toFixed(1)}</td>
                  <td className="font-mono">{vessel.drift_score.toFixed(1)}</td>
                  <td className="font-mono">
                    {vessel.behavioral_score !== undefined && vessel.behavioral_score !== null
                      ? vessel.behavioral_score.toFixed(1)
                      : '—'}
                  </td>
                  <td>
                    <div className="score-cell">
                      <span className="evidence-score font-mono font-bold">
                        {vessel.overall_evidence_score.toFixed(1)}
                      </span>
                      <span className="score-scale text-muted">/100</span>
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${badgeClass}`}>{vessel.classification}</span>
                  </td>
                  <td>
                    <ChevronRight size={14} className={`chevron-icon ${isSelected ? 'selected' : ''}`} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
