import React from 'react';
import { SpillDetection, SatelliteObservation } from '../types/contracts';
import { Target, Compass } from 'lucide-react';

interface SpillCardProps {
  spill: SpillDetection;
  observation: SatelliteObservation;
}

export const SpillCard: React.FC<SpillCardProps> = ({ spill, observation }) => {
  const hasConfidence = typeof spill.confidence === 'number';
  const confidencePercent = hasConfidence ? (spill.confidence * 100).toFixed(1) : null;
  const isDetected = Boolean(spill.detected);

  const hasArea = typeof spill.area === 'number';
  const hasPerimeter = typeof spill.perimeter === 'number';
  const hasOrientation = typeof spill.orientation === 'number';
  const hasCentroid = spill.centroid && typeof spill.centroid.latitude === 'number' && typeof spill.centroid.longitude === 'number';
  const hasBbox = spill.bounding_box && typeof spill.bounding_box.min_latitude === 'number';

  return (
    <div className="card spill-card">
      <div className="card-header">
        <div className="card-title-group">
          <Target size={16} className={isDetected ? 'text-cyan' : 'text-muted'} />
          <div>
            <h3 className="card-title">SAR Spill Characterization</h3>
            <span className="card-subtitle" style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'block' }}>
              SAR-based oil-spill detection result.
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <span className={`badge ${isDetected ? 'badge-cyan' : 'badge-low'}`}>
            {isDetected ? 'Oil Spill Detected' : 'No Spill Detected'}
          </span>
          {spill.detector_algorithm && (
            <span className="badge badge-outline font-mono" style={{ fontSize: '0.65rem' }}>
              {spill.detector_algorithm}
            </span>
          )}
        </div>
      </div>

      <div className="card-body">
        {/* Confidence Gauge */}
        <div className="metric-row">
          <div className="metric-label-group">
            <span className="metric-label">Detection Confidence</span>
            <span className="metric-highlight font-mono">
              {confidencePercent ? `${confidencePercent}%` : 'Not available'}
            </span>
          </div>
          <div className="progress-bar-bg">
            <div
              className={`progress-bar-fill ${isDetected ? 'fill-cyan' : 'fill-muted'}`}
              style={{ width: `${confidencePercent || 0}%` }}
            ></div>
          </div>
        </div>

        {/* Primary Metrics Grid */}
        <div className="stats-grid">
          <div className="stat-box">
            <span className="stat-label">Estimated Area</span>
            <span className="stat-value font-mono">
              {hasArea ? (
                <>
                  {spill.area} <span className="stat-unit">km²</span>
                </>
              ) : (
                'Not available'
              )}
            </span>
          </div>

          <div className="stat-box">
            <span className="stat-label">Perimeter</span>
            <span className="stat-value font-mono">
              {hasPerimeter ? (
                <>
                  {spill.perimeter} <span className="stat-unit">km</span>
                </>
              ) : (
                'Not available'
              )}
            </span>
          </div>

          <div className="stat-box">
            <span className="stat-label">Orientation</span>
            <div className="orientation-stat font-mono">
              {hasOrientation ? (
                <>
                  <span>{spill.orientation.toFixed(1)}°</span>
                  <Compass
                    size={14}
                    className="text-cyan"
                    style={{ transform: `rotate(${spill.orientation}deg)` }}
                  />
                </>
              ) : (
                'Not available'
              )}
            </div>
          </div>

          <div className="stat-box">
            <span className="stat-label">Look-Alike Risk</span>
            {spill.look_alike_risk ? (
              <span className={`badge badge-risk-${spill.look_alike_risk}`}>
                {spill.look_alike_risk.toUpperCase()}
              </span>
            ) : (
              <span className="font-mono text-muted" style={{ fontSize: '0.85rem' }}>
                Not available
              </span>
            )}
          </div>
        </div>

        {/* Centroid & Bounding Box */}
        <div className="coord-info-block">
          <div className="coord-row">
            <span className="coord-title">Slick Centroid:</span>
            <span className="coord-val font-mono">
              {hasCentroid ? (
                `${spill.centroid.latitude.toFixed(4)}°N, ${spill.centroid.longitude.toFixed(4)}°E`
              ) : (
                'Not available'
              )}
            </span>
          </div>
          <div className="coord-row">
            <span className="coord-title">Bounding Box:</span>
            <span className="coord-val font-mono">
              {hasBbox ? (
                `[${spill.bounding_box.min_latitude.toFixed(3)}°, ${spill.bounding_box.min_longitude.toFixed(3)}°] → [${spill.bounding_box.max_latitude.toFixed(3)}°, ${spill.bounding_box.max_longitude.toFixed(3)}°]`
              ) : (
                'Not available'
              )}
            </span>
          </div>
          <div className="coord-row">
            <span className="coord-title">SAR Sensor:</span>
            <span className="coord-val font-mono text-cyan">
              {observation?.sensor ? (
                `${observation.sensor} (${observation.resolution || 10}m/px)`
              ) : (
                'Not available'
              )}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
