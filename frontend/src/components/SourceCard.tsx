import React from 'react';
import { DriftResult, EnvironmentalState } from '../types/contracts';
import { History, Clock, Activity } from 'lucide-react';

interface SourceCardProps {
  drift: DriftResult;
  metocean: EnvironmentalState;
}

export const SourceCard: React.FC<SourceCardProps> = ({ drift, metocean }) => {
  if (!drift || !drift.source_centroid || !drift.release_time_window?.earliest) {
    return (
      <div className="card source-card">
        <div className="card-header">
          <div className="card-title-group">
            <History size={16} className="text-muted" />
            <h3 className="card-title">Lagrangian Source Reconstruction</h3>
          </div>
          <span className="badge badge-low">Not available</span>
        </div>
        <div className="card-body">
          <p className="text-muted" style={{ fontSize: '0.85rem', lineHeight: '1.5' }}>
            Lagrangian drift hindcasting is not available for this observation. Phase 2 focuses strictly on SAR detection; metocean forcing (ERA5/CMEMS) and backward drift will be computed in Phase 3.
          </p>
        </div>
      </div>
    );
  }

  const earliestUtc = new Date(drift.release_time_window.earliest).toUTCString().replace('GMT', 'UTC');
  const latestUtc = new Date(drift.release_time_window.latest).toUTCString().replace('GMT', 'UTC');
  const peakUtc = new Date(drift.release_time_window.most_probable).toUTCString().replace('GMT', 'UTC');

  const windSpeed = Math.sqrt(metocean.wind_u ** 2 + metocean.wind_v ** 2).toFixed(1);
  const currentSpeed = Math.sqrt(metocean.current_u ** 2 + metocean.current_v ** 2).toFixed(2);

  return (
    <div className="card source-card">
      <div className="card-header">
        <div className="card-title-group">
          <History size={16} className="text-amber" />
          <h3 className="card-title">Lagrangian Source Reconstruction</h3>
        </div>
        <span className="badge badge-amber font-mono">
          -{drift.drift_duration_hours}h Hindcast ({drift.particle_count} particles)
        </span>
      </div>

      <div className="card-body">
        {/* Source Centroid & Uncertainty Radius */}
        <div className="stats-grid">
          <div className="stat-box">
            <span className="stat-label">Source Centroid</span>
            <span className="stat-value font-mono text-amber">
              {drift.source_centroid.latitude.toFixed(4)}°N, {drift.source_centroid.longitude.toFixed(4)}°E
            </span>
          </div>

          <div className="stat-box">
            <span className="stat-label">Uncertainty Radius (95%)</span>
            <span className="stat-value font-mono">
              &plusmn;{drift.uncertainty.spatial_radius_km} <span className="stat-unit">km</span>
            </span>
          </div>

          <div className="stat-box">
            <span className="stat-label">Estimated Slick Age</span>
            <span className="stat-value font-mono">
              {drift.release_time_window.slick_age_hours_range[0]} -{' '}
              {drift.release_time_window.slick_age_hours_range[1]} <span className="stat-unit">hours</span>
            </span>
          </div>

          <div className="stat-box">
            <span className="stat-label">MetOcean Forcing</span>
            <span className="stat-value font-mono" style={{ fontSize: '0.85rem' }}>
              W: {windSpeed} m/s | C: {currentSpeed} m/s
            </span>
          </div>
        </div>

        {/* Release-Time Window Banner */}
        <div className="release-window-box">
          <div className="release-window-header">
            <Clock size={14} className="text-amber" />
            <span className="release-title">Probable Spill Release Window</span>
          </div>

          <div className="release-timeline-strip">
            <div className="timeline-node">
              <span className="node-tag">EARLIEST</span>
              <span className="node-time font-mono">{earliestUtc.split(' ').slice(1, 5).join(' ')}</span>
            </div>
            <div className="timeline-connector">&rarr;</div>
            <div className="timeline-node highlight-peak">
              <span className="node-tag text-amber">PEAK LIKELIHOOD</span>
              <span className="node-time font-mono text-amber">{peakUtc.split(' ').slice(1, 5).join(' ')}</span>
            </div>
            <div className="timeline-connector">&rarr;</div>
            <div className="timeline-node">
              <span className="node-tag">LATEST</span>
              <span className="node-time font-mono">{latestUtc.split(' ').slice(1, 5).join(' ')}</span>
            </div>
          </div>
        </div>

        {/* Physics Note */}
        <div className="physics-note">
          <Activity size={12} className="inline-icon text-muted" />
          <span>
            Monte Carlo backward advection via Runge-Kutta 2nd order with 3.2% wind leeway and horizontal eddy diffusivity D<sub>h</sub> = {drift.uncertainty.diffusion_coefficient} m²/s.
          </span>
        </div>
      </div>
    </div>
  );
};
