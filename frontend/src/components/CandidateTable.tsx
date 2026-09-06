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
            <h3 className="card-title">Candidate Vessel Filtering (Phase 5)</h3>
          </div>
          <span className="badge badge-low">No candidates</span>
        </div>
        <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
          <p style={{ margin: 0, fontSize: '0.9rem' }}>
            No AIS candidate vessels found within the spatio-temporal corridor. Spatio-temporal filtering matches historical vessel trajectories against the Phase 4 probable source region and release window.
          </p>
        </div>
      </div>
    );
  }

  const isPhase5View = candidates.some((c) => !!c.candidate_features);

  return (
    <div className="card candidate-table-card">
      <div className="card-header">
        <div className="card-title-group">
          <Ship size={16} className="text-cyan" />
          <h3 className="card-title">
            {isPhase5View ? 'Candidate Vessel Filtering (Phase 5)' : 'Candidate Vessel Correlation & Scoring'}
          </h3>
        </div>
        <span className="card-hint">
          {isPhase5View
            ? 'Click vessel to inspect kinematic CPA & trajectory features (Attribution in Phase 6)'
            : 'Click any vessel to inspect explainable evidence dossier'}
        </span>
      </div>

      <div className="table-responsive">
        <table className="candidate-table">
          <thead>
            {isPhase5View ? (
              <tr>
                <th style={{ width: '45px' }}>Rank</th>
                <th>Vessel Identification</th>
                <th>Type</th>
                <th title="Temporal alignment with Phase 4 release window">Temporal Match</th>
                <th title="Spatial alignment corridor with probable source region">Spatial Match</th>
                <th title="Closest Point of Approach (CPA) minimum distance to source centroid">Min Distance</th>
                <th title="Vessel traversed through probable source region polygon">Source Intersection</th>
                <th title="Trajectory quality (impossible speed / jump filtering)">Trajectory Quality</th>
                <th title="AIS transponder silence indicator">AIS Gap</th>
                <th>Status</th>
                <th style={{ width: '30px' }}></th>
              </tr>
            ) : (
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
            )}
          </thead>
          <tbody>
            {candidates.map((vessel, index) => {
              const isSelected = vessel.mmsi === selectedMmsi;
              const rank = index + 1;
              const feat = vessel.candidate_features;

              if (isPhase5View && feat) {
                const cpaKm = feat.closest_distance_km;
                const entered = feat.passed_through_source_region || feat.entered_source_region;
                const gapDetected = feat.ais_gap_detected || feat.ais_gap?.detected;

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
                          {feat.vessel_name || vessel.vessel_name || 'Unknown Vessel'}
                        </span>
                        <span className="vessel-mmsi font-mono text-muted">
                          MMSI: {vessel.mmsi}
                        </span>
                      </div>
                    </td>
                    <td className="text-muted">{feat.vessel_type || vessel.vessel_type || 'Commercial'}</td>
                    <td>
                      <span className="badge badge-high" style={{ fontSize: '0.72rem' }}>
                        COMPATIBLE
                      </span>
                    </td>
                    <td>
                      <span
                        className={`badge ${cpaKm <= 10.0 ? 'badge-high' : 'badge-medium'}`}
                        style={{ fontSize: '0.72rem' }}
                      >
                        {cpaKm <= 5.0 ? 'CORE PROXIMITY' : `${cpaKm.toFixed(1)} km`}
                      </span>
                    </td>
                    <td className="font-mono font-bold" style={{ color: '#00e5ff' }}>
                      {cpaKm.toFixed(2)} km
                    </td>
                    <td>
                      {entered ? (
                        <span className="badge badge-high" style={{ fontSize: '0.72rem' }}>
                          INTERSECTED
                        </span>
                      ) : (
                        <span className="badge badge-low" style={{ fontSize: '0.72rem' }}>
                          OUTSIDE
                        </span>
                      )}
                    </td>
                    <td style={{ fontSize: '0.78rem' }}>
                      <span className={feat.rejected_pings_count && feat.rejected_pings_count > 0 ? 'text-rose' : 'text-emerald'}>
                        {feat.trajectory_quality || 'Standard Quality'}
                      </span>
                    </td>
                    <td>
                      {gapDetected ? (
                        <span className="badge badge-low" style={{ fontSize: '0.72rem' }}>
                          GAP DETECTED
                        </span>
                      ) : (
                        <span className="badge badge-high" style={{ fontSize: '0.72rem' }}>
                          CONTINUOUS
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="badge badge-cyan" style={{ fontSize: '0.72rem' }}>
                        {feat.candidate_status || 'Candidate vessel'}
                      </span>
                    </td>
                    <td>
                      <ChevronRight size={14} className={`chevron-icon ${isSelected ? 'selected' : ''}`} />
                    </td>
                  </tr>
                );
              }

              // Classification Badge style for demo mode
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
